import os
import time
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.distributions.normal import Normal
from torch.distributions.categorical import Categorical
from torch.utils.tensorboard import SummaryWriter
import gymnasium as gym

from env.game_env import GamePlayerEnv
from training.expert_autopilot import NavigationExpert # Import your expert!

# --- Hyperparameters ---
LEARNING_RATE = 3e-4
TOTAL_TIMESTEPS = 1000000 # Total steps to train
NUM_STEPS = 2048 # Steps per PPO rollout
BATCH_SIZE = 64
GAMMA = 0.99
GAE_LAMBDA = 0.95
CLIP_COEF = 0.2
ENT_COEF = 0.01
VF_COEF = 0.5
MAX_GRAD_NORM = 0.5
UPDATE_EPOCHS = 10

# Phase-out settings
BC_COEF_START = 5.0       # Starting weight of the Expert's influence
PHASE_OUT_FRACTION = 0.5  # The expert phases out completely at 50% of total training

TRAINING_CELLS =["Vault111Ext"]

class MultiHeadAgent(nn.Module):
    def __init__(self):
        super().__init__()

        # --- FIX 1: Entity net takes 7 features (we ignore Index 6: FormID) ---
        self.entity_net = nn.Sequential(
            nn.Linear(7, 64),
            nn.LayerNorm(64),
            nn.ReLU(),
            nn.Linear(64, 64),
            nn.ReLU()
        )

        # Backbone takes 74 features (10 from player + 64 from pooled entities)
        self.backbone = nn.Sequential(
            nn.Linear(74, 128),
            nn.LayerNorm(128),
            nn.ReLU(),
            nn.Linear(128, 64),
            nn.ReLU()
        )

        self.actor_mouse_mean = nn.Sequential(nn.Linear(64, 2), nn.Tanh())
        self.actor_mouse_logstd = nn.Parameter(torch.zeros(1, 2))
        self.actor_movement = nn.Linear(64, 5)
        self.actor_jump = nn.Linear(64, 2)

        # --- NEW ACTION HEADS ---
        self.actor_lmb = nn.Linear(64, 2)
        self.actor_rmb = nn.Linear(64, 2)
        self.actor_e = nn.Linear(64, 2)

        self.critic = nn.Linear(64, 1)

    def process_obs(self, obs):
        p_state = obs["player_state"].clone()
        ents = obs["entities"].clone()

        p_xyz = p_state[:, 0:3]
        norm_p_xyz = p_xyz / 1000.0

        yaw = p_state[:, 3:4]
        pitch = p_state[:, 4:5]

        sin_yaw = torch.sin(yaw)
        cos_yaw = torch.cos(yaw)
        sin_pitch = torch.sin(pitch)
        cos_pitch = torch.cos(pitch)

        norm_p_angles = torch.cat([sin_yaw, cos_yaw, sin_pitch, cos_pitch], dim=1)
        norm_p_stats = p_state[:, 5:8] / 100.0

        # Player State: 3 + 4 + 3 = 10 Dims
        norm_p_state = torch.cat([norm_p_xyz, norm_p_angles, norm_p_stats], dim=1)

        # Entity State: 3 + 1 + 1 + 1 + 1 = 7 Dims
        rel_xyz = (ents[:, :, 0:3] - p_xyz.unsqueeze(1)) / 1000.0
        norm_type = ents[:, :, 3:4] / 100.0
        norm_dist = ents[:, :, 4:5] / 1000.0
        norm_hostile = ents[:, :, 5:6]
        # (Skip Index 6, FormId)
        norm_is_target = ents[:, :, 7:8]

        # --- FIX 2: Correctly concatenate exactly 7 features ---
        norm_ents = torch.cat([rel_xyz, norm_type, norm_dist, norm_hostile, norm_is_target], dim=-1)

        ent_features = self.entity_net(norm_ents)
        pooled_ents, _ = torch.max(ent_features, dim=1)

        return torch.cat([norm_p_state, pooled_ents], dim=1)

    def get_value(self, x):
        features = self.backbone(self.process_obs(x))
        return self.critic(features)

    def get_action_and_value(self, x, act_mouse=None, act_mov=None, act_jump=None, act_lmb=None, act_rmb=None, act_e=None):
        features = self.backbone(self.process_obs(x))

        mouse_mean = self.actor_mouse_mean(features)
        mouse_std = torch.exp(self.actor_mouse_logstd.expand_as(mouse_mean))
        dist_mouse = Normal(mouse_mean, mouse_std)

        dist_mov = Categorical(logits=self.actor_movement(features))
        dist_jump = Categorical(logits=self.actor_jump(features))
        dist_lmb = Categorical(logits=self.actor_lmb(features))
        dist_rmb = Categorical(logits=self.actor_rmb(features))
        dist_e = Categorical(logits=self.actor_e(features))

        if act_mouse is None: act_mouse = dist_mouse.sample()
        if act_mov is None: act_mov = dist_mov.sample()
        if act_jump is None: act_jump = dist_jump.sample()
        if act_lmb is None: act_lmb = dist_lmb.sample()
        if act_rmb is None: act_rmb = dist_rmb.sample()
        if act_e is None: act_e = dist_e.sample()

        logprob = (dist_mouse.log_prob(act_mouse).sum(1) +
                   dist_mov.log_prob(act_mov) +
                   dist_jump.log_prob(act_jump) +
                   dist_lmb.log_prob(act_lmb) +
                   dist_rmb.log_prob(act_rmb) +
                   dist_e.log_prob(act_e))

        entropy = (dist_mouse.entropy().sum(1) +
                   dist_mov.entropy() +
                   dist_jump.entropy() +
                   dist_lmb.entropy() +
                   dist_rmb.entropy() +
                   dist_e.entropy())

        return act_mouse, act_mov, act_jump, act_lmb, act_rmb, act_e, logprob, entropy, self.critic(features)


def make_env():
    def thunk():
        return GamePlayerEnv(max_entities=64, training_cells=TRAINING_CELLS)
    return thunk

def main():
    run_name = f"F4_Agent_OnlineExpert_{int(time.time())}"
    writer = SummaryWriter(f"runs/{run_name}")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    num_envs = 1
    envs = gym.vector.SyncVectorEnv([make_env() for _ in range(num_envs)])
    agent = MultiHeadAgent().to(device)
    optimizer = optim.Adam(agent.parameters(), lr=LEARNING_RATE, eps=1e-5)

    # Initialize one expert per environment instance
    experts = [NavigationExpert() for _ in range(num_envs)]

    # --- PPO Buffers ---
    obs_player = torch.zeros((NUM_STEPS, num_envs, 8)).to(device)
    obs_ents = torch.zeros((NUM_STEPS, num_envs, 64, 8)).to(device)
    actions_mouse = torch.zeros((NUM_STEPS, num_envs, 2)).to(device)
    actions_mov = torch.zeros((NUM_STEPS, num_envs)).to(device)
    actions_jump = torch.zeros((NUM_STEPS, num_envs)).to(device)
    actions_lmb = torch.zeros((NUM_STEPS, num_envs)).to(device)
    actions_rmb = torch.zeros((NUM_STEPS, num_envs)).to(device)
    actions_e = torch.zeros((NUM_STEPS, num_envs)).to(device)

    # --- EXPERT BUFFERS (For the auxiliary loss) ---
    exp_actions_mouse = torch.zeros((NUM_STEPS, num_envs, 2)).to(device)
    exp_actions_mov = torch.zeros((NUM_STEPS, num_envs), dtype=torch.long).to(device)
    exp_actions_jump = torch.zeros((NUM_STEPS, num_envs), dtype=torch.long).to(device)

    exp_active_mask = torch.zeros((NUM_STEPS, num_envs)).to(device)

    logprobs = torch.zeros((NUM_STEPS, num_envs)).to(device)
    rewards = torch.zeros((NUM_STEPS, num_envs)).to(device)
    dones = torch.zeros((NUM_STEPS, num_envs)).to(device)
    values = torch.zeros((NUM_STEPS, num_envs)).to(device)

    global_step = 0
    obs, _ = envs.reset()
    next_obs = {
        "player_state": torch.Tensor(obs["player_state"]).to(device),
        "entities": torch.Tensor(obs["entities"]).to(device)
    }
    next_done = torch.zeros(num_envs).to(device)

    num_updates = TOTAL_TIMESTEPS // NUM_STEPS

    for update in range(1, num_updates + 1):
        # 0. Calculate Expert Phase-out Weight
        # Decays linearly from BC_COEF_START to 0 over the first 50% of training
        frac = 1.0 - (global_step / (TOTAL_TIMESTEPS * PHASE_OUT_FRACTION))
        current_bc_weight = max(0.0, BC_COEF_START * frac)

        # 1. Rollout Phase
        for step in range(0, NUM_STEPS):
            global_step += num_envs
            obs_player[step] = next_obs["player_state"]
            obs_ents[step] = next_obs["entities"]
            dones[step] = next_done

            # Get Agent Action
            with torch.no_grad():
                act_mouse, act_mov, act_jump, act_lmb, act_rmb, act_e, logprob, _, value = agent.get_action_and_value(next_obs)
                values[step] = value.flatten()

            actions_mouse[step] = act_mouse
            actions_mov[step] = act_mov
            actions_jump[step] = act_jump
            actions_lmb[step] = act_lmb
            actions_rmb[step] = act_rmb
            actions_e[step] = act_e
            logprobs[step] = logprob

            # --- EXPERT INTERVENTION ---
            # Even though the agent controls the game, the Expert watches and records its ideal moves
            for i in range(num_envs):
                p_state = next_obs["player_state"][i].cpu().numpy()
                ents = next_obs["entities"][i].cpu().numpy()

                player_xyz = p_state[0:3]
                pyaw, ppitch = p_state[3:5]

                exp_mouse = np.array([0.0, 0.0], dtype=np.float32)
                exp_mov = 0
                exp_jump = 0 # Default to no jump

                if experts[i].check_if_stuck(player_xyz):
                    exp_mov = 2 # S (Backup)
                    exp_jump = experts[i].should_jump(player_xyz) # Jump to get unstuck
                    experts[i].backing_up_frames -= 1
                else:
                    target_xyz = experts[i].select_target(ents, player_xyz)
                    is_active = 1.0 if (target_xyz is not None or experts[i].backing_up_frames > 0) else 0.0
                    exp_active_mask[step][i] = is_active
                    if target_xyz is not None:
                        exp_mouse = experts[i].get_smooth_aim(player_xyz, (pyaw, ppitch), target_xyz)
                        steer = experts[i].analyze_obstacles(ents, player_xyz, pyaw)
                        exp_mov = steer if steer else 1 # W (Forward)

                        # <-- Check if we need to jump up to the target
                        exp_jump = experts[i].should_jump(player_xyz, target_xyz)

                exp_actions_mouse[step][i] = torch.as_tensor(exp_mouse)
                exp_actions_mov[step][i] = torch.as_tensor(exp_mov, dtype=torch.long)
                exp_actions_jump[step][i] = torch.as_tensor(exp_jump, dtype=torch.long)
            # ---------------------------
            # Step environment using the AGENT's actions
            step_action = {
                "mouse_delta": torch.clamp(act_mouse, -1.0, 1.0).cpu().numpy(),
                "movement": act_mov.cpu().numpy(),
                "jump": act_jump.cpu().numpy(),
                "click_lmb": act_lmb.cpu().numpy(),
                "click_rmb": act_rmb.cpu().numpy(),
                "press_e": act_e.cpu().numpy()
            }
            obs, reward, terminated, truncated, info = envs.step(step_action)

            rewards[step] = torch.tensor(reward).to(device).view(-1)
            next_obs = {
                "player_state": torch.Tensor(obs["player_state"]).to(device),
                "entities": torch.Tensor(obs["entities"]).to(device)
            }
            next_done = torch.Tensor(terminated | truncated).to(device)

        # 2. Advantage Calculation
        with torch.no_grad():
            next_value = agent.get_value(next_obs).reshape(1, -1)
            advantages = torch.zeros_like(rewards).to(device)
            lastgaelam = 0
            for t in reversed(range(NUM_STEPS)):
                if t == NUM_STEPS - 1:
                    nextnonterminal = 1.0 - next_done
                    nextvalues = next_value
                else:
                    nextnonterminal = 1.0 - dones[t + 1]
                    nextvalues = values[t + 1]
                delta = rewards[t] + GAMMA * nextvalues * nextnonterminal - values[t]
                advantages[t] = lastgaelam = delta + GAMMA * GAE_LAMBDA * nextnonterminal * lastgaelam
            returns = advantages + values

        # 3. Optimize Phase (PPO + Expert Distillation)
        b_obs = {
            "player_state": obs_player.reshape(-1, 8),
            "entities": obs_ents.reshape(-1, 64, 8)
        }
        b_act_mouse = actions_mouse.reshape(-1, 2)
        b_act_mov = actions_mov.reshape(-1)
        b_act_jump = actions_jump.reshape(-1)
        b_act_lmb = actions_lmb.reshape(-1)
        b_act_rmb = actions_rmb.reshape(-1)
        b_act_e = actions_e.reshape(-1)

        # Expert flattened tensors
        b_exp_mouse = exp_actions_mouse.reshape(-1, 2)
        b_exp_mov = exp_actions_mov.reshape(-1)
        b_exp_jump = exp_actions_jump.reshape(-1)

        b_logprobs = logprobs.reshape(-1)
        b_advantages = advantages.reshape(-1)
        b_returns = returns.reshape(-1)
        b_values = values.reshape(-1)

        b_advantages = (b_advantages - b_advantages.mean()) / (b_advantages.std() + 1e-8)

        # Loss functions for mimicking the expert
        mse_loss_fn = nn.MSELoss(reduction='none')
        ce_loss_fn = nn.CrossEntropyLoss(reduction='none')
        b_mask = exp_active_mask.reshape(-1)

        # Pass our batched data through the network
        for epoch in range(UPDATE_EPOCHS):
            features = agent.backbone(agent.process_obs(b_obs))


            # --- AGENT LOGIC (PPO Loss) ---
            _, _, _, _, _, _, newlogprob, entropy, newvalue = agent.get_action_and_value(
                b_obs, b_act_mouse, b_act_mov, b_act_jump, b_act_lmb, b_act_rmb, b_act_e
            )
            logratio = newlogprob - b_logprobs
            ratio = logratio.exp()
            pg_loss1 = -b_advantages * ratio
            pg_loss2 = -b_advantages * torch.clamp(ratio, 1 - CLIP_COEF, 1 + CLIP_COEF)
            pg_loss = torch.max(pg_loss1, pg_loss2).mean()
            v_loss = 0.5 * ((newvalue.view(-1) - b_returns) ** 2).mean()

            # --- EXPERT LOGIC (Auxiliary BC Loss) ---
            bc_loss = 0.0
            if current_bc_weight > 0.0:
                pred_mouse_mean = agent.actor_mouse_mean(features)
                pred_mov_logits = agent.actor_movement(features)
                pred_jump_logits = agent.actor_jump(features)

                # Calculate unreduced losses
                loss_mouse_raw = mse_loss_fn(pred_mouse_mean, b_exp_mouse).mean(dim=1)
                loss_mov_raw = ce_loss_fn(pred_mov_logits, b_exp_mov)
                loss_jump_raw = ce_loss_fn(pred_jump_logits, b_exp_jump)

                # Mask out inactive expert frames, then take the mean!
                loss_mouse = (loss_mouse_raw * b_mask).sum() / (b_mask.sum() + 1e-8)
                loss_mov = (loss_mov_raw * b_mask).sum() / (b_mask.sum() + 1e-8)
                loss_jump = (loss_jump_raw * b_mask).sum() / (b_mask.sum() + 1e-8)

                # Balance the weights. CE Loss (0 to 2.0) naturally dominates MSE (-1 to 1).
                bc_loss = (loss_mouse * 5.0) + (loss_mov * 0.5) + (loss_jump * 0.1)

            # --- FINAL COMBINED LOSS ---
            # We add the expert penalty, scaled by the decaying weight
            loss = pg_loss - ENT_COEF * entropy.mean() + v_loss * VF_COEF + (current_bc_weight * bc_loss)

            optimizer.zero_grad()
            loss.backward()
            nn.utils.clip_grad_norm_(agent.parameters(), MAX_GRAD_NORM)
            optimizer.step()

        # Logging
        writer.add_scalar("losses/value_loss", v_loss.item(), global_step)
        writer.add_scalar("losses/policy_loss", pg_loss.item(), global_step)
        if current_bc_weight > 0.0:
            writer.add_scalar("losses/expert_loss", bc_loss.item(), global_step)
        writer.add_scalar("charts/expert_weight", current_bc_weight, global_step)
        writer.add_scalar("rewards/mean_reward", rewards.mean().item(), global_step)

        print(f"Update: {update} | Mean Reward: {rewards.mean().item():.3f} | Expert Wt: {current_bc_weight:.2f}")

if __name__ == "__main__":
    main()
