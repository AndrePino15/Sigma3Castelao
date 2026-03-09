# SAFEGOALS – Smart Stadium Seat System

> **S**tadium **A**ssistance and **F**an **E**ngagement with **G**ame-day **O**ptimised **A**ctive **L**ighting and **S**ound

**Σ3 Design Exercise – Team Castelão** | University of Southampton · ELEC2300

---

SAFEGOALS is a distributed electronic system designed to enhance the stadium experience through interactive fan engagement, accessibility features, and safety systems.

This repository contains the complete prototype implementation developed during the ELEC2300 Σ3 System Design Exercise at the University of Southampton. The system integrates embedded hardware, networking infrastructure, distributed control software, and real-time audio streaming into a scalable architecture capable of supporting thousands of stadium seats.

---

## Table of Contents

- [Overview](#overview)
- [System Architecture](#system-architecture)
- [Key Features](#key-features)
- [Hardware Architecture](#hardware-architecture)
- [Software Architecture](#software-architecture)
- [Communication Architecture](#communication-architecture)
- [Audio Streaming System](#audio-streaming-system)
- [Safety System](#safety-system)
- [Scalability](#scalability)
- [Repository Structure](#repository-structure)
- [Development Context](#development-context)
- [Authors](#authors)
- [License](#license)

---

## Overview

Modern stadiums are evolving from passive viewing spaces into interactive entertainment environments. SAFEGOALS proposes a seat-integrated electronic platform that allows spectators to actively participate in events while improving safety and accessibility.

Each seat becomes a networked node capable of:

- Detecting occupancy
- Displaying coordinated LED lighting animations
- Allowing fan interaction via buttons
- Sending emergency alerts
- Delivering live match commentary audio

The system is designed around a **hierarchical architecture**:

```
Central Server
      │
Wi-Fi / Ethernet Network
      │
Section Controller (Raspberry Pi)
      │
High-speed CAN Bus
      │
Seat Nodes (Microcontroller devices)
```

This architecture allows the system to scale from a single prototype to tens of thousands of seats in a stadium.

---

## System Architecture

![System Architecture Block Diagram](docs/system_architecture.png)

The system is divided into four major subsystems:

| Subsystem | Description |
|---|---|
| **Seat Node** | Embedded hardware device in each seat |
| **Section Controller** | Edge compute gateway per stadium section |
| **Central Server** | Coordination and control of the full system |
| **Premium Seat Touchscreen** | Optional enhanced interface for premium seats |

Each subsystem communicates through defined network interfaces to maintain modularity and scalability.

---

## Key Features

### 🎉 Fan Engagement
- Coordinated LED animations across stadium sections
- Crowd voting and interactive participation
- Synchronised lighting effects during key moments (goals, celebrations)

### ♿ Accessibility
- Real-time match commentary delivered through a headphone jack
- Supports spectators requiring assisted listening

### 🚨 Safety
- Dedicated emergency assistance button at every seat
- Rapid alert transmission to stadium staff
- Visual guidance through LED lighting during evacuation scenarios

### 📡 Scalability
- CAN bus architecture supports hundreds of seats per section
- Section controllers distribute processing load
- Server provides central orchestration

### 🔧 Modular Design
- **Base tier seats** provide core functionality
- **Premium seats** add a touchscreen interface featuring:
  - Live statistics
  - Instant replays
  - Food ordering
  - Enhanced fan interaction

---

## Hardware Architecture

### Seat Node

The seat node is the lowest-level embedded device installed in each stadium seat.

**Functions:**
- Seat occupancy sensing
- LED bar control
- Button input for fan voting
- Emergency assistance button
- CAN communication with section controller
- Audio output jack

**Typical hardware components:**
- Microcontroller
- CAN transceiver
- LED driver circuitry
- Seat occupancy sensor
- Audio output stage

> Seat nodes are designed to be extremely low cost, enabling deployment at stadium scale.

### Section Controller

The section controller acts as a gateway between seat nodes and the central server.

**Implementation:** Raspberry Pi 3B+

**Responsibilities:**
- CAN bus management
- Communication with hundreds of seat nodes
- Wi-Fi/Ethernet communication with the server
- Audio streaming playback
- System synchronisation

Each controller manages a single stadium section.

### Central Server

The server coordinates the entire system.

**Responsibilities:**
- Broadcasting commands to section controllers
- Managing lighting animations
- Running fan voting events
- Handling safety alerts
- Managing audio streaming sources

The server ensures synchronisation across multiple stadium sections.

### Premium Seat Touchscreen

Premium seats can include an optional **7-inch touchscreen** display providing a richer fan experience.

**Possible features:**
- Live statistics
- Instant replay clips
- Stadium services (food ordering)
- Enhanced voting interfaces

The touchscreen communicates with the system through the same network infrastructure as other components.

---

## Software Architecture

The software stack is divided into four major modules:

```
software/
│
├── seat-controller/        # Embedded firmware running on seat nodes
│
├── section-controller/     # Raspberry Pi gateway software
│
├── server/                 # Central coordination server
│
└── touchscreen/            # Premium seat interface
```

---

## Communication Architecture

SAFEGOALS uses multiple communication layers matched to the requirements of each system tier.

### CAN Bus

**Used between:** Seat Nodes ↔ Section Controller

**Advantages:**
- Reliable and deterministic
- Low latency
- Suitable for long wiring runs

**CAN frames transmit:**
- Sensor data
- Button events
- LED commands
- Status messages

### Network Communication

**Used between:** Section Controller ↔ Central Server

**Transport:** Wi-Fi or Ethernet

**Protocols:**
- MQTT (control messages)
- UDP (audio streaming)

This allows central orchestration while keeping local seat control distributed.

---

## Audio Streaming System

The system supports live stadium commentary streaming directly to seat headphone jacks — no smartphone required.

**Pipeline:**

```
Audio Source
     │
Central Server
     │
UDP / RTP Stream
     │
Section Controller
     │
Audio Playback
     │
Seat Headphone Jack
```

---

## Safety System

Safety is a core design objective of SAFEGOALS.

Each seat node includes a dedicated **SOS emergency button**. Pressing the button triggers:

1. A CAN message sent to the section controller
2. A notification forwarded to the central server
3. Logging of the seat location
4. An alert dispatched to stadium staff

The lighting system can also switch to **evacuation mode**, guiding spectators toward exits using coordinated LED patterns.

---

## Scalability

The hierarchical architecture is designed to support large real-world stadium deployments.

**Example at stadium scale:**

| Metric | Value |
|---|---|
| Total seats | ~40,000 |
| Stadium sections | ~100 |
| Seats per section | ~400 |

**Benefits of the hierarchical approach:**
- Reduces network congestion
- Distributes processing across section controllers
- Simplifies maintenance and fault isolation

---

## Repository Structure

```
SAFEGOALS/
│
├── hardware/               # Schematics, PCB designs, and hardware documentation
│
├── software/
│   ├── seat-controller/    # Firmware for seat node microcontrollers
│   ├── section-controller/ # Raspberry Pi software (CAN bus + network communication)
│   ├── server/             # Central system controller and coordination logic
│   └── touchscreen/        # Software for premium seat displays
│
├── docs/                   # System diagrams and design documentation
│
└── README.md
```

---

## Development Context

This project was developed as part of the **ELEC2300 Σ3 System Design Exercise** at the University of Southampton.

The exercise challenges student teams to design and prototype a seat-integrated stadium technology platform combining entertainment, safety, sensing, and audio functionality.

The project was completed over a **7-week design cycle** including:

1. Research and system design
2. Prototyping and development
3. Hardware construction
4. Integration and testing
5. Live demonstration at a trade fair

---

## Authors

**Team Castelão**

- Andre Teixeira Pino
- Zihao Wang
- Finlay Radford
- Nereesha Kurukulasuriya
- Emre Canogullari
- Dongchi Xu

---

## License

This repository is provided for educational and demonstration purposes.
