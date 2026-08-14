# Guitar Wiring Simulator

Guitar Wiring Simulator (GWS) is a Python/Tkinter application for designing and analyzing passive electric-guitar wiring. English and Korean interfaces are included.

## Installation and running

Python 3.10 or later, Git, and Tkinter are required. No third-party Python packages are needed.

```powershell
git clone https://github.com/ashdown124/gws.git
cd gws
python main.py
```

On Windows, the application can also be started with `app.bat`.

## Features

- Arrange pickups, potentiometers, resistors, capacitors, switches, a jack, and ground on a canvas.
- Connect terminals with editable wires and junctions.
- Save component options, positions, and wiring as a diagram.
- Automatically analyze output magnitude and phase across 50-5000 Hz.

## Saving and loading diagrams

Diagrams are saved as `.gws` files. A diagram contains the components, their positions and options, and all wiring information. The current file format is version 1.

## Custom switches

Custom switches can be added as `.gcs` files in the [`custom_switch`](custom_switch) folder. Each file defines the switch name, terminal arrangement, positions, and terminal connections.

See the [custom switch guide](custom_switch/README.md) for the file format.
