using NUnit.Framework;
using Unity.Collections;
using Unity.Entities;
using Unity.Mathematics;
using MadFactory.Core;
using MadFactory.ECS;

namespace MadFactory.Tests.EditMode.Tilemap
{
    [TestFixture]
    public class TilemapInitializationSystemTests
    {
        private World _world;
        private EntityManager _em;

        [SetUp]
        public void SetUp()
        {
            _world = new World("TestWorld");
            _em = _world.EntityManager;
        }

        [TearDown]
        public void TearDown()
        {
            // Dispose any TilemapSingleton tiles before disposing world
            using var query = _em.CreateEntityQuery(typeof(TilemapSingleton));
            if (query.CalculateEntityCount() > 0)
            {
                var singleton = query.GetSingleton<TilemapSingleton>();
                if (singleton.Tiles.IsCreated)
                    singleton.Tiles.Dispose();
            }
            _world.Dispose();
        }

        [Test]
        public void Initialize_CreatesMapWith4096Tiles()
        {
            var system = _world.GetOrCreateSystem<TilemapInitializationSystem>();
            system.Update(_world.Unmanaged);

            using var query = _em.CreateEntityQuery(typeof(TilemapSingleton));
            var singleton = query.GetSingleton<TilemapSingleton>();

            Assert.AreEqual(new int2(64, 64), singleton.MapSize);
            Assert.AreEqual(4096, singleton.Tiles.Length);
        }

        [Test]
        public void Initialize_AllTilesAreGround()
        {
            var system = _world.GetOrCreateSystem<TilemapInitializationSystem>();
            system.Update(_world.Unmanaged);

            using var query = _em.CreateEntityQuery(typeof(TilemapSingleton));
            var singleton = query.GetSingleton<TilemapSingleton>();

            for (int i = 0; i < singleton.Tiles.Length; i++)
            {
                Assert.AreEqual(TerrainType.Ground, singleton.Tiles[i].Terrain,
                    $"Tile at index {i} should be Ground");
            }
        }

        [Test]
        public void Initialize_IronOreArea_HasIronOre()
        {
            var system = _world.GetOrCreateSystem<TilemapInitializationSystem>();
            system.Update(_world.Unmanaged);

            using var query = _em.CreateEntityQuery(typeof(TilemapSingleton));
            var singleton = query.GetSingleton<TilemapSingleton>();

            for (int y = 27; y <= 36; y++)
            {
                for (int x = 27; x <= 36; x++)
                {
                    var index = TilemapHelper.CoordToIndex(new int2(x, y), singleton.MapSize);
                    Assert.AreEqual(ResourceType.IronOre, singleton.Tiles[index].Resource,
                        $"Tile at ({x},{y}) should have IronOre");
                }
            }
        }

        [Test]
        public void Initialize_OutsideIronOreArea_HasNone()
        {
            var system = _world.GetOrCreateSystem<TilemapInitializationSystem>();
            system.Update(_world.Unmanaged);

            using var query = _em.CreateEntityQuery(typeof(TilemapSingleton));
            var singleton = query.GetSingleton<TilemapSingleton>();

            // Check a tile outside the iron ore area
            var index = TilemapHelper.CoordToIndex(new int2(0, 0), singleton.MapSize);
            Assert.AreEqual(ResourceType.None, singleton.Tiles[index].Resource);

            index = TilemapHelper.CoordToIndex(new int2(26, 26), singleton.MapSize);
            Assert.AreEqual(ResourceType.None, singleton.Tiles[index].Resource);

            index = TilemapHelper.CoordToIndex(new int2(37, 37), singleton.MapSize);
            Assert.AreEqual(ResourceType.None, singleton.Tiles[index].Resource);
        }

        [Test]
        public void Initialize_WhenSingletonExists_DoesNotDuplicate()
        {
            // Create a singleton manually first
            var existingTiles = new NativeArray<TileData>(4096, Allocator.Persistent);
            var existingEntity = _em.CreateEntity();
            _em.AddComponentData(existingEntity, new TilemapSingleton
            {
                MapSize = new int2(64, 64),
                Tiles = existingTiles
            });

            var system = _world.GetOrCreateSystem<TilemapInitializationSystem>();
            system.Update(_world.Unmanaged);

            using var query = _em.CreateEntityQuery(typeof(TilemapSingleton));
            Assert.AreEqual(1, query.CalculateEntityCount(),
                "Should not create a duplicate singleton");
        }
    }
}
