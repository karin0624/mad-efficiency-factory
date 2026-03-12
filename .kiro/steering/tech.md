# Technology Stack

## Architecture

Hybrid ECS approach:
- **Core simulation** runs on an ECS-like tick system (resource flow, belt transport, machine processing)
- **Rendering & input** handled by Godot's scene tree (Camera, Input, ECS-to-graphics bridge)
- **UI** via Godot's Control nodes (device palette, delivery counter, HUD)

Separation principle: game logic is pure data + systems with no Godot dependency; Godot nodes are thin adapters for rendering and input.

## Core Technologies

- **Engine**: Godot 4.x
- **Language**: GDScript (primary), C# (optional for performance-critical systems)
- **Platform**: Linux/WSL2 native development, cross-platform export

## Key Libraries

- Godot built-in tilemap system for grid-based world
- Godot signals for event-driven communication between systems

## Development Standards

### Code Quality
- Game logic separated from engine code (testable without Godot runtime)
- No global singletons for game state; use dependency injection or autoload sparingly
- Event-driven communication between systems (Godot signals / custom event bus)

### Testing
- Layer 1 (Unit): Pure logic classes tested without engine dependency
- Layer 2 (Integration): Component interaction tests within Godot
- Layer 3 (Human Review): Visual quality and game feel verified manually

## Development Environment

### Required Tools
- Godot 4.x editor
- Git + GitHub CLI (`gh`)

### Common Commands
```bash
# Run project: godot --path godot/
# Run tests: (TBD based on test framework choice)
# Export: godot --headless --export-release
```

## Key Technical Decisions

- **Godot over Unity**: Native Linux/WSL2 support eliminates complex bind-mount and MCP bridge workarounds
- **Hybrid ECS**: Pure data+systems for simulation tick; Godot scene tree only for presentation
- **Tile-based world**: Grid coordinates for factory layout; tilemap for rendering

---
_Document standards and patterns, not every dependency_
