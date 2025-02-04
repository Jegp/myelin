import torch

from myelin.torch.functional.lif import (
    LIFFeedForwardState,
    LIFParameters,
    lif_feed_forward_step,
)
from myelin.torch.functional.leaky_integrator import LIState

from myelin.torch.module.leaky_integrator import LICell
from myelin.torch.module.lif import LIFFeedForwardCell


class ConvNet(torch.nn.Module):
    def __init__(
        self, device, num_channels=1, feature_size=28, model="super", dtype=torch.float
    ):
        super(ConvNet, self).__init__()
        self.features = int(((feature_size - 4) / 2 - 4) / 2)
        self.conv1 = torch.nn.Conv2d(num_channels, 20, 5, 1)
        self.conv2 = torch.nn.Conv2d(20, 50, 5, 1)
        self.fc1 = torch.nn.Linear(self.features * self.features * 50, 500)
        self.out = LICell(500, 10)
        self.device = device
        self.lif0 = LIFFeedForwardCell(
            (20, feature_size - 4, feature_size - 4),
            p=LIFParameters(model=model, alpha=100.0),
        )
        self.lif1 = LIFFeedForwardCell(
            (50, int((feature_size - 4) / 2) - 4, int((feature_size - 4) / 2) - 4),
            p=LIFParameters(model=model, alpha=100.0),
        )
        self.lif2 = LIFFeedForwardCell(
            (500,), p=LIFParameters(model=model, alpha=100.0)
        )
        self.dtype = dtype

    def forward(self, x):
        seq_length = x.shape[0]
        batch_size = x.shape[1]

        # specify the initial states
        s0 = self.lif0.initial_state(batch_size, self.device, self.dtype)
        s1 = self.lif1.initial_state(batch_size, self.device, self.dtype)
        s2 = self.lif2.initial_state(batch_size, self.device, self.dtype)
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
            z = z.view(-1, self.features ** 2 * 50)
            z = self.fc1(z)
            z, s2 = self.lif2(z, s2)
            v, so = self.out(torch.nn.functional.relu(z), so)
            voltages[ts, :, :] = v
        return voltages


class ConvNet4(torch.nn.Module):
    def __init__(
        self, device, num_channels=1, feature_size=28, model="super", dtype=torch.float
    ):
        super(ConvNet4, self).__init__()
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
