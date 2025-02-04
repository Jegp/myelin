.. note::
    :class: sphx-glr-download-link-note

    Click :ref:`here <sphx_glr_download_auto_examples_plot_mnist.py>` to download the full example code
.. rst-class:: sphx-glr-example-title

.. _sphx_glr_auto_examples_plot_mnist.py:


Spiking Neural Networks
=======================

Spiking neural networks are not that much different than Artificial Neural
Networks that are currently most commonly in use. The main difference is
that there is an insistence that communication between units in the network
happens through spikes - represented as binary one or zero - and that time
is involved.

How to define a Network
-----------------------

The spiking neural network primitives in myelin are designed to fit in as seamlessly
as possible into a traditional deep learning pipeline.


.. code-block:: default


    import torch
    from myelin.torch.functional.lif import (
        LIFParameters,
    )

    from myelin.torch.module.leaky_integrator import LICell
    from myelin.torch.module.lif import LIFFeedForwardCell


    class Net(torch.nn.Module):
        def __init__(
                self,
                device="cpu",
                num_channels=1,
                feature_size=32,
                model="super",
                dtype=torch.float,
        ):
            super(Net, self).__init__()
            self.features = int(((feature_size - 4) / 2 - 4) / 2)

            self.conv1 = torch.nn.Conv2d(num_channels, 32, 5, 1)
            self.conv2 = torch.nn.Conv2d(32, 64, 5, 1)
            self.fc1 = torch.nn.Linear(self.features * self.features * 64, 1024)
            self.lif0 = LIFFeedForwardCell(
                (32, feature_size - 4, feature_size - 4),
                p=LIFParameters(method=model, alpha=100.0),
            )
            self.lif1 = LIFFeedForwardCell(
                (64, int((feature_size - 4) / 2) - 4, int((feature_size - 4) / 2) - 4),
                p=LIFParameters(method=model, alpha=100.0),
            )
            self.lif2 = LIFFeedForwardCell(
                (1024,), p=LIFParameters(method=model, alpha=100.0)
            )
            self.out = LICell(1024, 10)
            self.device = device
            self.dtype = dtype

        def forward(self, x):
            seq_length = x.shape[0]
            batch_size = x.shape[1]

            # specify the initial states
            s0 = self.lif0.initial_state(batch_size, device=self.device, dtype=self.dtype)
            s1 = self.lif1.initial_state(batch_size, device=self.device, dtype=self.dtype)
            s2 = self.lif2.initial_state(batch_size, device=self.device, dtype=self.dtype)
            so = self.out.initial_state(batch_size, device=self.device, dtype=self.dtype)

            voltages = torch.zeros(
                seq_length, batch_size, 10, device=self.device, dtype=self.dtype
            )

            for ts in range(seq_length):
                z = self.conv1(x[ts, :])
                z, s0 = self.lif0(z, s0)
                z = torch.nn.functional.max_pool2d(z, 2, 2)
                z = 10 * self.conv2(z)
                z, s1 = self.lif1(z, s1)
                z = torch.nn.functional.max_pool2d(z, 2, 2)
                z = z.view(-1, self.features ** 2 * 64)
                z = self.fc1(z)
                z, s2 = self.lif2(z, s2)
                v, so = self.out(torch.nn.functional.relu(z), so)
                voltages[ts, :, :] = v
            return voltages


    net = Net()
    print(net)





.. rst-class:: sphx-glr-script-out

 Out:

 .. code-block:: none

    Net(
      (conv1): Conv2d(1, 32, kernel_size=(5, 5), stride=(1, 1))
      (conv2): Conv2d(32, 64, kernel_size=(5, 5), stride=(1, 1))
      (fc1): Linear(in_features=1600, out_features=1024, bias=True)
      (lif0): LIFFeedForwardCell((32, 28, 28), p=LIFParameters(tau_syn_inv=tensor(200.), tau_mem_inv=tensor(100.), v_leak=tensor(0.), v_th=tensor(1.), v_reset=tensor(0.), method='super', alpha=100.0), dt=0.001)
      (lif1): LIFFeedForwardCell((64, 10, 10), p=LIFParameters(tau_syn_inv=tensor(200.), tau_mem_inv=tensor(100.), v_leak=tensor(0.), v_th=tensor(1.), v_reset=tensor(0.), method='super', alpha=100.0), dt=0.001)
      (lif2): LIFFeedForwardCell((1024,), p=LIFParameters(tau_syn_inv=tensor(200.), tau_mem_inv=tensor(100.), v_leak=tensor(0.), v_th=tensor(1.), v_reset=tensor(0.), method='super', alpha=100.0), dt=0.001)
      (out): LICell()
    )



We can evaluate the network we just defined on an input of size 1x32x32.
Note that in contrast to typical spiking neural network simulators time
is just another dimension in the input tensor here we chose to evaluate
the network on 16 timesteps and there is an explicit batch dimension
(number of concurrently evaluated inputs with identical model parameters).


.. code-block:: default


    timesteps = 16
    batch_size = 1
    input = torch.abs(torch.randn(timesteps, batch_size, 1, 32, 32))
    out = net(input)
    print(out)






.. rst-class:: sphx-glr-script-out

 Out:

 .. code-block:: none

    tensor([[[0., 0., 0., 0., 0., 0., 0., 0., 0., 0.]],

            [[0., 0., 0., 0., 0., 0., 0., 0., 0., 0.]],

            [[0., 0., 0., 0., 0., 0., 0., 0., 0., 0.]],

            [[0., 0., 0., 0., 0., 0., 0., 0., 0., 0.]],

            [[0., 0., 0., 0., 0., 0., 0., 0., 0., 0.]],

            [[0., 0., 0., 0., 0., 0., 0., 0., 0., 0.]],

            [[0., 0., 0., 0., 0., 0., 0., 0., 0., 0.]],

            [[0., 0., 0., 0., 0., 0., 0., 0., 0., 0.]],

            [[0., 0., 0., 0., 0., 0., 0., 0., 0., 0.]],

            [[0., 0., 0., 0., 0., 0., 0., 0., 0., 0.]],

            [[0., 0., 0., 0., 0., 0., 0., 0., 0., 0.]],

            [[0., 0., 0., 0., 0., 0., 0., 0., 0., 0.]],

            [[0., 0., 0., 0., 0., 0., 0., 0., 0., 0.]],

            [[0., 0., 0., 0., 0., 0., 0., 0., 0., 0.]],

            [[0., 0., 0., 0., 0., 0., 0., 0., 0., 0.]],

            [[0., 0., 0., 0., 0., 0., 0., 0., 0., 0.]]], grad_fn=<CopySlices>)



Since the spiking neural network is implemented as a pytorch module, we
can use the usual pytorch primitives for optimizing it. Note that the
backward computation expects a gradient for each timestep


.. code-block:: default


    net.zero_grad()
    out.backward(torch.randn(timesteps, batch_size, 10))







.. note::

    ``myelin`` like pytorch only supports mini-batches. This means that
    contrary to most other spiking neural network simulators ```myelin``` always
    integrates several indepdentent sets of spiking neural networks at once.


.. rst-class:: sphx-glr-timing

   **Total running time of the script:** ( 0 minutes  0.809 seconds)


.. _sphx_glr_download_auto_examples_plot_mnist.py:


.. only :: html

 .. container:: sphx-glr-footer
    :class: sphx-glr-footer-example



  .. container:: sphx-glr-download

     :download:`Download Python source code: plot_mnist.py <plot_mnist.py>`



  .. container:: sphx-glr-download

     :download:`Download Jupyter notebook: plot_mnist.ipynb <plot_mnist.ipynb>`


.. only:: html

 .. rst-class:: sphx-glr-signature

    `Gallery generated by Sphinx-Gallery <https://sphinx-gallery.github.io>`_
