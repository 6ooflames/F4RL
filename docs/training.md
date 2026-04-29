# Training Paradigms

F4RL has undergone a significant evolution in its learning approach, moving from static datasets to dynamic, online interaction.

## 1. Legacy: Behavioral Cloning (BC)
Previously, the project utilized a Behavioral Cloning approach. This involved:
* Collecting "Expert" trajectories (human or scripted gameplay).
* Saving these transitions as pickled datasets.
* Training a model to mimic the distribution of the expert's actions.

While useful for establishing a baseline, BC suffered from "distribution shift," where the agent would fail when encountering states not present in the original dataset.

## 2. Current: Online Reinforcement Learning
The current focus is on **Online Learning** using the **CleanRL** implementation. 
* **The Loop:** The agent interacts with the live game, receives rewards based on the current state, and updates its policy in real-time.
* **Advantages:** This allows the agent to discover novel strategies and adapt to the environment's dynamics without the need for pre-recorded datasets.

## Roadmap & Known Limitations
* **Data Exfiltration Bottleneck:** The current training efficiency is limited by the amount of data the `ModShim` plugin can exfiltrate. As the plugin is updated to provide more granular entity data, the complexity of the agent's "world view" will increase.
* **Reward Shaping:** Current reward logic (such as distance-based tracking) is a placeholder. Future iterations will implement more complex, multi-objective reward functions as the `ModShim` data becomes more robust.
* **Targeting Logic:** The current "lock-on" behavior for reward calculation is a temporary implementation intended to be replaced by a more sophisticated entity-relationship model.
