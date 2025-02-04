# adapted from https://github.com/pytorch/examples/blob/master/reinforcement_learning/reinforce.py
# for license see LICENSE.cartpole

import torch
import numpy as np
from absl import app
from absl import flags
from absl import logging
import random
import os
import gym


from myelin.torch.functional.lif import LIFParameters
from myelin.torch.module.lif import LIFConstantCurrentEncoder, LIFCell
from myelin.torch.module.leaky_integrator import LICell

FLAGS = flags.FLAGS


class ANNPolicy(torch.nn.Module):
    def __init__(self, device="cpu"):
        super(ANNPolicy, self).__init__()
        self.state_space = 4
        self.action_space = 2
        self.l1 = torch.nn.Linear(self.state_space, 128, bias=False)
        self.l2 = torch.nn.Linear(128, self.action_space, bias=False)
        self.dropout = torch.nn.Dropout(p=0.6)

        self.saved_log_probs = []
        self.rewards = []

    def forward(self, x):
        x = self.l1(x)
        x = self.dropout(x)
        x = torch.nn.functional.relu(x)
        x = self.l2(x)
        x = torch.nn.functional.softmax(x)
        return x


class Policy(torch.nn.Module):
    def __init__(self, device="cpu"):
        super(Policy, self).__init__()
        self.state_dim = 4
        self.input_features = 16
        self.hidden_features = 128
        self.output_features = 2
        self.device = device
        self.constant_current_encoder = LIFConstantCurrentEncoder(
            40, device=self.device
        )
        self.lif = LIFCell(
            2 * self.state_dim,
            self.hidden_features,
            p=LIFParameters(method="super", alpha=100.0),
        )
        self.dropout = torch.nn.Dropout(p=0.5)
        self.readout = LICell(self.hidden_features, self.output_features)

        self.saved_log_probs = []
        self.rewards = []

    def forward(self, x):
        scale = 50
        x = x.to(self.device)
        _, x_pos = self.constant_current_encoder(torch.nn.functional.relu(scale * x))
        _, x_neg = self.constant_current_encoder(torch.nn.functional.relu(-scale * x))
        x = torch.cat([x_pos, x_neg], dim=2)

        seq_length, batch_size, _ = x.shape

        # state for hidden layer
        s1 = self.lif.initial_state(batch_size, device=self.device)
        # state for output layer
        so = self.readout.initial_state(batch_size, device=self.device)

        voltages = torch.zeros(
            seq_length, batch_size, self.output_features, device=self.device
        )

        # sequential integration loop
        for ts in range(seq_length):
            z1, s1 = self.lif(x[ts, :, :], s1)
            z1 = self.dropout(z1)
            vo, so = self.readout(z1, so)
            voltages[ts, :, :] = vo

        m, _ = torch.max(voltages, 0)
        p_y = torch.nn.functional.softmax(m, dim=1)
        return p_y


class LSNNPolicy(torch.nn.Module):
    def __init__(self, device="cpu", model="super"):
        super(LSNNPolicy, self).__init__()
        self.state_dim = 4
        self.input_features = 16
        self.hidden_features = 128
        self.output_features = 2
        self.device = device
        # self.affine1 = torch.nn.Linear(self.state_dim, self.input_features)
        self.constant_current_encoder = snn.LIFConstantCurrentEncoder(
            40, device=self.device
        )
        self.lif_layer = snn.LSNNCell(2 * self.state_dim, self.hidden_features)
        self.dropout = torch.nn.Dropout(p=0.5)
        self.readout = snn.LICell(self.hidden_features, self.output_features)

        self.saved_log_probs = []
        self.rewards = []

    def forward(self, x):
        scale = 50
        _, x_pos = self.constant_current_encoder(torch.nn.functional.relu(scale * x))
        _, x_neg = self.constant_current_encoder(torch.nn.functional.relu(-scale * x))
        x = torch.cat([x_pos, x_neg], dim=2)

        seq_length, batch_size, _ = x.shape

        # state for hidden layer
        s1 = self.lif_layer.initial_state(batch_size, device=self.device)
        # state for output layer
        so = self.readout.initial_state(batch_size, device=self.device)

        voltages = torch.zeros(
            seq_length, batch_size, self.output_features, device=self.device
        )

        # sequential integration loop
        for ts in range(seq_length):
            z1, s1 = self.lif_layer(x[ts, :, :], z1, v1, i1, b1)
            z1 = self.dropout(z1)
            so = self.readout(z1, so)
            voltages[ts, :, :] = so.v

        m, _ = torch.max(voltages, 0)
        p_y = torch.nn.functional.softmax(m, dim=1)
        return p_y


def select_action(state, policy, device):
    state = torch.from_numpy(state).float().unsqueeze(0).to(device)
    probs = policy(state)
    m = torch.distributions.Categorical(probs)
    action = m.sample()
    policy.saved_log_probs.append(m.log_prob(action))
    return action.item()


def finish_episode(policy, optimizer):
    eps = np.finfo(np.float32).eps.item()
    R = 0
    policy_loss = []
    returns = []
    for r in policy.rewards[::-1]:
        R = r + FLAGS.gamma * R
        returns.insert(0, R)
    returns = torch.tensor(returns)
    returns = (returns - returns.mean()) / (returns.std() + eps)
    for log_prob, R in zip(policy.saved_log_probs, returns):
        policy_loss.append(-log_prob * R)
    optimizer.zero_grad()
    policy_loss = torch.cat(policy_loss).sum()
    policy_loss.backward()
    optimizer.step()
    del policy.rewards[:]
    del policy.saved_log_probs[:]


def main(argv):
    running_reward = 10
    torch.manual_seed(FLAGS.random_seed)
    random.seed(FLAGS.random_seed)

    label = f"{FLAGS.policy}-{FLAGS.model}-{FLAGS.random_seed}"
    os.makedirs(f"runs/cartpole/{label}", exist_ok=True)
    os.chdir(f"runs/cartpole/{label}")
    FLAGS.append_flags_into_file(f"flags.txt")

    np.random.seed(FLAGS.random_seed)
    if hasattr(torch, "cuda_is_available"):
        if torch.cuda_is_available():
            torch.cuda.manual_seed(FLAGS.random_seed)

    env = gym.make(FLAGS.environment)
    env.reset()
    env.seed(FLAGS.random_seed)

    if FLAGS.policy == "ann":
        policy = ANNPolicy()
    elif FLAGS.policy == "snn":
        policy = Policy()
    elif FLAGS.policy == "lsnn":
        policy = LSNNPolicy(device=FLAGS.device, model=FLAGS.model).to(FLAGS.device)
    optimizer = torch.optim.Adam(policy.parameters(), lr=FLAGS.learning_rate)

    running_rewards = []
    episode_rewards = []

    for e in range(FLAGS.episodes):
        state, ep_reward = env.reset(), 0

        for t in range(1, 10000):  # Don't infinite loop while learning
            action = select_action(state, policy, device=FLAGS.device)
            state, reward, done, _ = env.step(action)
            if FLAGS.render:
                env.render()
            policy.rewards.append(reward)
            ep_reward += reward
            if done:
                break

        running_reward = 0.05 * ep_reward + (1 - 0.05) * running_reward
        finish_episode(policy, optimizer)

        if e % FLAGS.log_interval == 0:
            logging.info(
                "Episode {}/{} \tLast reward: {:.2f}\tAverage reward: {:.2f}".format(
                    e, FLAGS.episodes, ep_reward, running_reward
                )
            )
        episode_rewards.append(ep_reward)
        running_rewards.append(running_reward)
        if running_reward > env.spec.reward_threshold:
            logging.info(
                "Solved! Running reward is now {} and "
                "the last episode runs to {} time steps!".format(running_reward, t)
            )
            break

    np.save(f"running_rewards.npy", np.array(running_rewards))
    np.save(f"episode_rewards.npy", np.array(episode_rewards))
    torch.save(optimizer.state_dict(), f"optimizer.pt")
    torch.save(policy.state_dict(), f"policy.pt")


if __name__ == "__main__":
    app.run(main)
