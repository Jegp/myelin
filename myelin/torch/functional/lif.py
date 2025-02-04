from typing import NamedTuple, Tuple

import torch
import torch.jit

from .threshhold import threshhold


class LIFParameters(NamedTuple):
    """Parametrization of a LIF neuron
    
    Parameters:
        tau_syn_inv (torch.Tensor): inverse synaptic time constant (:math:`1/\\tau_\\text{syn}`)
        tau_mem_inv (torch.Tensor): inverse membrane time constant (:math:`1/\\tau_\\text{mem}`)
        v_leak (torch.Tensor): leak potential
        v_th (torch.Tensor): threshhold potential
        v_reset (torch.Tensor): reset potential
        method (str): method to determine the spike threshold (relevant for surrogate gradients)
        alpha (float): hyper parameter to use in surrogate gradient computation
    """

    tau_syn_inv: torch.Tensor = torch.tensor(1.0 / 5e-3)
    tau_mem_inv: torch.Tensor = torch.tensor(1.0 / 1e-2)
    v_leak: torch.Tensor = torch.tensor(0.0)
    v_th: torch.Tensor = torch.tensor(1.0)
    v_reset: torch.Tensor = torch.tensor(0.0)
    method: str = "super"
    alpha: float = 0.0


class LIFState(NamedTuple):
    """State of a LIF neuron

    Parameters:
        z (torch.Tensor): recurrent spikes
        v (torch.Tensor): membrane potential
        i (torch.Tensor): synaptic input current
    """

    z: torch.Tensor
    v: torch.Tensor
    i: torch.Tensor


class LIFFeedForwardState(NamedTuple):
    """State of a feed forward LIF neuron

    Parameters:
        v (torch.Tensor): membrane potential
        i (torch.Tensor): synaptic input current
    """

    v: torch.Tensor
    i: torch.Tensor


def lif_step(
    input: torch.Tensor,
    s: LIFState,
    input_weights: torch.Tensor,
    recurrent_weights: torch.Tensor,
    p: LIFParameters = LIFParameters(),
    dt: float = 0.001,
) -> Tuple[torch.Tensor, LIFState]:
    r"""Computes a single euler-integration step of a LIF neuron-model. More
    specifically it implements one integration step of the following ODE

    .. math::
        \begin{align*}
            \dot{v} &= 1/\tau_{\text{mem}} (v_{\text{leak}} - v + i) \\
            \dot{i} &= -1/\tau_{\text{syn}} i
        \end{align*}

    together with the jump condition
    
    .. math::
        z = \Theta(v - v_{\text{th}})
    
    and transition equations

    .. math::
        \begin{align*}
            v &= (1-z) v + z v_{\text{reset}} \\
            i &= i + w_{\text{input}} z_{\text{in}} \\
            i &= i + w_{\text{rec}} z_{\text{rec}}
        \end{align*}

    where :math:`z_{\text{rec}}` and :math:`z_{\text{in}}` are the recurrent and input
    spikes respectively.

    Parameters:
        input (torch.Tensor): the input spikes at the current time step
        s (LIFState): current state of the LIF neuron
        input_weights (torch.Tensor): synaptic weights for incoming spikes
        recurrent_weights (torch.Tensor): synaptic weights for recurrent spikes
        p (LIFParameters): parameters of a leaky integrate and fire neuron
        dt (float): Integration timestep to use
    """
    # compute voltage updates
    dv = dt * p.tau_mem_inv * ((p.v_leak - s.v) + s.i)
    v_decayed = s.v + dv

    # compute current updates
    di = -dt * p.tau_syn_inv * s.i
    i_decayed = s.i + di

    # compute new spikes
    z_new = threshhold(v_decayed - p.v_th, p.method, p.alpha)
    # compute reset
    v_new = (1 - z_new) * v_decayed + z_new * p.v_reset
    # compute current jumps
    i_new = (
        i_decayed
        + torch.nn.functional.linear(input, input_weights)
        + torch.nn.functional.linear(s.z, recurrent_weights)
    )

    return z_new, LIFState(z_new, v_new, i_new)


def lif_feed_forward_step(
    input: torch.Tensor,
    s: LIFFeedForwardState,
    p: LIFParameters = LIFParameters(),
    dt: float = 0.001,
) -> Tuple[torch.Tensor, LIFFeedForwardState]:
    r"""Computes a single euler-integration step for a lif neuron-model.
    It takes as input the input current as generated by an arbitrary torch module
    or function. More specifically it implements one integration step of the following ODE

    .. math::
        \begin{align*}
            \dot{v} &= 1/\tau_{\text{mem}} (v_{\text{leak}} - v + i) \\
            \dot{i} &= -1/\tau_{\text{syn}} i
        \end{align*}

    together with the jump condition
    
    .. math::
        z = \Theta(v - v_{\text{th}})
    
    and transition equations

    .. math::
        \begin{align*}
            v &= (1-z) v + z v_{\text{reset}} \\
            i &= i + i_{\text{in}}
        \end{align*}

    where :math:`i_{\text{in}}` is meant to be the result of applying an arbitrary
    pytorch module (such as a convolution) to input spikes.

    Parameters:
        input (torch.Tensor): the input spikes at the current time step
        s (LIFFeedForwardState): current state of the LIF neuron
        p (LIFParameters): parameters of a leaky integrate and fire neuron
        dt (float): Integration timestep to use
    """
    # compute voltage updates
    dv = dt * p.tau_mem_inv * ((p.v_leak - s.v) + s.i)
    v_decayed = s.v + dv

    # compute current updates
    di = -dt * p.tau_syn_inv * s.i
    i_decayed = s.i + di

    # compute new spikes
    z_new = threshhold(v_decayed - p.v_th, p.method, p.alpha)
    # compute reset
    v_new = (1 - z_new) * v_decayed + z_new * p.v_reset
    # compute current jumps
    i_new = i_decayed + input

    return z_new, LIFFeedForwardState(v_new, i_new)


def lif_current_encoder(
    input_current: torch.Tensor,
    v: torch.Tensor,
    p: LIFParameters = LIFParameters(),
    dt: float = 0.001,
):
    dv = dt * p.tau_mem_inv * ((p.v_leak - v) + input_current)
    v = v + dv
    z = threshhold(v - p.v_th, p.method, p.alpha)

    v = v - z * (v - p.v_reset)
    return z, v
