# Custom Switch Definitions

Store user-defined switches in this folder as `*.gcs` text files.

## Format

```text
[Name]
Dual On-On-On
[Grid]
2 3
[Position]
"P1" (0,2), (1,3);
"P2" (0,2), (3,5);
"P3" (2,4), (3,5);
```

- Enter the language-independent switch name after `[Name]`.
- Enter two integers after `[Grid]` in `columns rows` order. `2 3` creates six terminals in two columns and three rows.
- Under `[Position]`, enter each position name followed by the terminal pairs connected in that position.
- Enclose position names in double quotes.
- Write connections as `(terminal,terminal)`, separate pairs with commas, and end each position with a semicolon (`;`).

Terminal numbering starts at the upper-left and increases from left to right across each row:

```text
3 columns, 2 rows

0   1   2
3   4   5
```

A terminal cannot appear in more than one connection pair within the same position. Valid definitions appear at the bottom of the Switch Type list as `[custom] Name`, using the language-independent value from their `[Name]` section.

The `[Name]` value is also the stable identifier stored in `.gws` diagrams, so every custom switch must use a unique name. File names may be changed freely and may contain spaces, Unicode characters, and uppercase letters, except for characters prohibited by the operating system.

If a referenced `[Name]` is unavailable while loading a diagram, the missing switch and wires connected through it are omitted while the remaining diagram is loaded.
