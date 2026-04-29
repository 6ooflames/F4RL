import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from torch.utils.tensorboard import SummaryWriter
import numpy as np
import pickle
import os

class StateBasedAgent(nn.Module):
    """
    State-Based Neural Network Architecture.
    Uses DeepSets (MLP + MaxPool) for permutation-invariant entity processing,
    combined with MLPs for player state.
    """
    def __init__(self, max_entities=50, entity_dim=6, player_dim=8):
        super(StateBasedAgent, self).__init__()

        # Entity Network: (B, N, 6) -> (B, N, 64)
        self.entity_net = nn.Sequential(
            nn.Linear(entity_dim, 64),
            nn.ReLU(),
            nn.Linear(64, 64),
            nn.ReLU()
        )

        # Player Network: (B, 8) -> (B, 64)
        self.player_net = nn.Sequential(
            nn.Linear(player_dim, 64),
            nn.ReLU()
        )

        # Trunk: (B, 128) -> (B, 128)
        self.trunk = nn.Sequential(
            nn.Linear(128, 128),
            nn.ReLU(),
            nn.Linear(128, 128),
            nn.ReLU()
        )

        # Heads
        self.mouse_head = nn.Sequential(
            nn.Linear(128, 2),
            nn.Tanh() # Bounded [-1, 1] for relative mouse movement
        )
        self.movement_head = nn.Linear(128, 5) # Discrete (Idle, W, S, A, D)
        self.buttons_head = nn.Linear(128, 4)  # MultiBinary (Attack, Block, Jump, Interact)

    def forward(self, player_state, entities):
        # Process entities (DeepSets approach)
        e_features = self.entity_net(entities)
        e_agg, _ = torch.max(e_features, dim=1) # Permutation invariant max pooling

        # Process player state
        p_features = self.player_net(player_state)

        # Concatenate and pass through trunk
        combined = torch.cat([p_features, e_agg], dim=-1)
        trunk_out = self.trunk(combined)

        # Predict actions
        mouse_delta = self.mouse_head(trunk_out)
        movement_logits = self.movement_head(trunk_out)
        button_logits = self.buttons_head(trunk_out)

        return mouse_delta, movement_logits, button_logits

class ExpertDataset(Dataset):
    def __init__(self, data_path):
        with open(data_path, 'rb') as f:
            self.data = pickle.load(f)

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):
        transition = self.data[idx]
        obs = transition["obs"]
        action = transition["action"]

        player_state = torch.tensor(obs["player_state"], dtype=torch.float32)
        entities = torch.tensor(obs["entities"], dtype=torch.float32)

        mouse_delta = torch.tensor(action["mouse_delta"], dtype=torch.float32)
        movement = torch.tensor(action["movement"], dtype=torch.long)
        buttons = torch.tensor(action["buttons"], dtype=torch.float32)

        return player_state, entities, mouse_delta, movement, buttons

def train_bc():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Training Behavioral Cloning on: {device}")

    data_path = "expert_data_RedRocketExt.pkl"
    if not os.path.exists(data_path):
        print(f"Error: Expert dataset {data_path} not found. Run expert_autopilot.py first.")
        return

    dataset = ExpertDataset(data_path)
    # Split into train and val (80/20)
    train_size = int(0.8 * len(dataset))
    val_size = len(dataset) - train_size
    train_dataset, val_dataset = torch.utils.data.random_split(dataset, [train_size, val_size])

    train_loader = DataLoader(train_dataset, batch_size=64, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=64, shuffle=False)

    model = StateBasedAgent().to(device)
    optimizer = optim.Adam(model.parameters(), lr=1e-3)

    # Loss functions for dict action space
    mse_loss = nn.MSELoss()
    ce_loss = nn.CrossEntropyLoss()
    bce_loss = nn.BCEWithLogitsLoss()

    writer = SummaryWriter(log_dir="runs/bc_training")

    epochs = 2500
    for epoch in range(epochs):
        model.train()
        train_loss = 0.0

        for p_state, ents, m_delta, mov, btns in train_loader:
            p_state, ents = p_state.to(device), ents.to(device)
            m_delta, mov, btns = m_delta.to(device), mov.to(device), btns.to(device)

            optimizer.zero_grad()

            pred_mouse, pred_mov, pred_btns = model(p_state, ents)

            l_mouse = mse_loss(pred_mouse, m_delta)
            l_mov = ce_loss(pred_mov, mov)
            l_btns = bce_loss(pred_btns, btns)

            loss = l_mouse + l_mov + l_btns
            loss.backward()
            optimizer.step()

            train_loss += loss.item()

        train_loss /= len(train_loader)

        # Validation
        model.eval()
        val_loss = 0.0
        with torch.no_grad():
            for p_state, ents, m_delta, mov, btns in val_loader:
                p_state, ents = p_state.to(device), ents.to(device)
                m_delta, mov, btns = m_delta.to(device), mov.to(device), btns.to(device)

                pred_mouse, pred_mov, pred_btns = model(p_state, ents)

                l_mouse = mse_loss(pred_mouse, m_delta)
                l_mov = ce_loss(pred_mov, mov)
                l_btns = bce_loss(pred_btns, btns)

                val_loss += (l_mouse + l_mov + l_btns).item()

        val_loss /= len(val_loader)

        print(f"Epoch [{epoch+1}/{epochs}] | Train Loss: {train_loss:.4f} | Val Loss: {val_loss:.4f}")
        writer.add_scalar('Loss/Train', train_loss, epoch)
        writer.add_scalar('Loss/Validation', val_loss, epoch)

    # Save the pre-trained weights
    torch.save(model.state_dict(), "bc_baseline.pth")
    print("Training complete. Model saved as bc_baseline.pth")
    writer.close()

if __name__ == "__main__":
    train_bc()
