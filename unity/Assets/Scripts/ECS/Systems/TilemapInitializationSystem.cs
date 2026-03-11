using Unity.Burst;
using Unity.Collections;
using Unity.Entities;
using Unity.Mathematics;
using MadFactory.Core;

namespace MadFactory.ECS
{
    [BurstCompile]
    public partial struct TilemapInitializationSystem : ISystem
    {
        private static readonly int2 MapSize = new int2(64, 64);
        private static readonly int2 IronOreOrigin = new int2(27, 27);
        private static readonly int2 IronOreEnd = new int2(36, 36);

        [BurstCompile]
        public void OnCreate(ref SystemState state)
        {
            // Check if singleton already exists
            var query = state.EntityManager.CreateEntityQuery(typeof(TilemapSingleton));
            if (query.CalculateEntityCount() > 0)
            {
                state.Enabled = false;
                return;
            }

            var totalTiles = MapSize.x * MapSize.y;
            var tiles = new NativeArray<TileData>(totalTiles, Allocator.Persistent);

            // Initialize all tiles to Ground terrain with no resource
            for (int i = 0; i < totalTiles; i++)
            {
                tiles[i] = new TileData
                {
                    Terrain = TerrainType.Ground,
                    Resource = ResourceType.None,
                    OccupyingEntity = Entity.Null
                };
            }

            // Set iron ore area (27,27) to (36,36) inclusive
            for (int y = IronOreOrigin.y; y <= IronOreEnd.y; y++)
            {
                for (int x = IronOreOrigin.x; x <= IronOreEnd.x; x++)
                {
                    var index = TilemapHelper.CoordToIndex(new int2(x, y), MapSize);
                    var tile = tiles[index];
                    tile.Resource = ResourceType.IronOre;
                    tiles[index] = tile;
                }
            }

            // Create singleton entity
            var entity = state.EntityManager.CreateEntity();
            state.EntityManager.AddComponentData(entity, new TilemapSingleton
            {
                MapSize = MapSize,
                Tiles = tiles
            });

            // Disable system after initialization
            state.Enabled = false;
        }

        [BurstCompile]
        public void OnUpdate(ref SystemState state)
        {
            // Intentionally empty - system is disabled after OnCreate
        }

        [BurstCompile]
        public void OnDestroy(ref SystemState state)
        {
            var query = state.EntityManager.CreateEntityQuery(typeof(TilemapSingleton));
            if (query.CalculateEntityCount() > 0)
            {
                var singleton = query.GetSingleton<TilemapSingleton>();
                if (singleton.Tiles.IsCreated)
                {
                    singleton.Tiles.Dispose();
                }
            }
        }
    }
}
