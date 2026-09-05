# Guitar Wiring Simulator

Guitar Wiring Simulator (GWS) is a Python/Tkinter application for designing and analyzing passive electric-guitar wiring. English and Korean interfaces are included.

Current release: **1.1.0**

## Installation and running

Python 3.10 or later, Git, and Tkinter are required. No third-party Python packages are needed.

```powershell
git clone https://github.com/ashdown124/gws.git
cd gws
python main.py
```

On Windows, the application can also be started with `app.bat`.

## Basic usage

- Select a component from the palette, add it to the canvas, and drag it into place.
- Click a terminal to begin wiring, add nodes on the canvas, and click another terminal to complete the connection.
- Select components or wires to edit their options. Potentiometers and switches can be adjusted with the mouse wheel.

The application includes an in-app controls guide for selection, wiring, and keyboard shortcuts.

## Signal simulation

Signal analysis runs automatically when pickups are connected to the output jack. The output voltage and phase spectra are displayed across 0-7000 Hz.

## Saving and loading diagrams

Diagrams are saved as `.gws` files. A diagram contains the components, their positions and options, and all wiring information. The current file format is version 1.

## Custom switches

Custom switches can be added as `.gcs` files in the [`custom_switch`](custom_switch) folder. Each file defines the switch name, terminal arrangement, positions, and terminal connections.

See the [custom switch guide](custom_switch/README.md) for the file format.
