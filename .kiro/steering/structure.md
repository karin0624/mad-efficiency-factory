# Project Structure

## Organization Philosophy

Feature-layered approach: core game logic is engine-agnostic, with Godot-specific code in a separate layer. This enables unit testing without the engine and keeps simulation deterministic.

## Directory Patterns

### Core Logic (`godot/scripts/core/`)
**Purpose**: Pure game logic — resource types, tile data, belt simulation, machine processing
**Rules**: No `extends Node` or Godot-specific imports. Plain GDScript classes or C# POCOs.
**Example**: `resource_type.gd`, `tile_data.gd`, `tilemap_helper.gd`

### ECS / Systems (`godot/scripts/systems/`)
**Purpose**: Tick-driven simulation systems (belt transport, machine processing, resource flow)
**Rules**: Operate on data components, no direct scene tree access
**Example**: `belt_transport_system.gd`, `machine_process_system.gd`

### Scenes & Nodes (`godot/scenes/`)
**Purpose**: Godot scene files (.tscn) and their attached scripts
**Rules**: Thin adapters — delegate logic to core/systems, handle rendering and input
**Example**: `main.tscn`, `factory_grid.tscn`, `conveyor_belt.tscn`

### UI (`godot/scenes/ui/`)
**Purpose**: HUD, menus, palettes using Godot Control nodes
**Example**: `hud.tscn`, `device_palette.tscn`, `delivery_counter.tscn`

### Tests (`godot/tests/`)
**Purpose**: GdUnit4 or compatible test framework
**Pattern**: Mirror source structure — `tests/core/test_tilemap_helper.gd`

### Specs (`.kiro/specs/`)
**Purpose**: Per-feature specification documents (requirements, design, tasks)
**Pattern**: One directory per feature, managed by cc-sdd pipeline

## Naming Conventions

- **GDScript files**: snake_case (`belt_transport_system.gd`)
- **Scene files**: snake_case (`factory_grid.tscn`)
- **Classes**: PascalCase (`class_name BeltTransportSystem`)
- **Signals**: snake_case past tense (`item_delivered`, `machine_started`)
- **Constants**: UPPER_SNAKE_CASE

## Code Organization Principles

- **Logic ≠ Presentation**: Core logic must not reference Godot nodes. Godot scripts bridge data to visuals.
- **Signal-driven**: Cross-system communication uses Godot signals or a custom event bus, not direct references.
- **No deep inheritance**: Prefer composition over inheritance. Scenes compose behaviors via child nodes.

---
_Document patterns, not file trees. New files following patterns shouldn't require updates_
