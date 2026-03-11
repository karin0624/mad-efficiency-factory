using NUnit.Framework;
using Unity.Collections;
using Unity.Entities;
using Unity.Mathematics;
using MadFactory.Core;

namespace MadFactory.Tests.EditMode.Tilemap
{
    [TestFixture]
    public class TilemapHelperTests
    {
        private static readonly int2 DefaultMapSize = new int2(64, 64);

        #region CoordToIndex

        [Test]
        public void CoordToIndex_Origin_ReturnsZero()
        {
            var result = TilemapHelper.CoordToIndex(new int2(0, 0), DefaultMapSize);
            Assert.AreEqual(0, result);
        }

        [Test]
        public void CoordToIndex_ValidCoord_ReturnsCorrectIndex()
        {
            // index = y * mapSize.x + x = 3 * 64 + 5 = 197
            var result = TilemapHelper.CoordToIndex(new int2(5, 3), DefaultMapSize);
            Assert.AreEqual(197, result);
        }

        #endregion

        #region IsInBounds

        [Test]
        public void IsInBounds_ValidCoord_ReturnsTrue()
        {
            var result = TilemapHelper.IsInBounds(new int2(10, 10), DefaultMapSize);
            Assert.IsTrue(result);
        }

        [Test]
        public void IsInBounds_NegativeX_ReturnsFalse()
        {
            var result = TilemapHelper.IsInBounds(new int2(-1, 0), DefaultMapSize);
            Assert.IsFalse(result);
        }

        [Test]
        public void IsInBounds_NegativeY_ReturnsFalse()
        {
            var result = TilemapHelper.IsInBounds(new int2(0, -1), DefaultMapSize);
            Assert.IsFalse(result);
        }

        [Test]
        public void IsInBounds_XExceedsBounds_ReturnsFalse()
        {
            var result = TilemapHelper.IsInBounds(new int2(64, 0), DefaultMapSize);
            Assert.IsFalse(result);
        }

        [Test]
        public void IsInBounds_YExceedsBounds_ReturnsFalse()
        {
            var result = TilemapHelper.IsInBounds(new int2(0, 64), DefaultMapSize);
            Assert.IsFalse(result);
        }

        [Test]
        public void IsInBounds_EdgeCoord63_ReturnsTrue()
        {
            var result = TilemapHelper.IsInBounds(new int2(63, 63), DefaultMapSize);
            Assert.IsTrue(result);
        }

        #endregion

        #region IsOccupied

        [Test]
        public void IsOccupied_EmptyTile_ReturnsFalse()
        {
            var tiles = CreateDefaultTiles();
            var result = TilemapHelper.IsOccupied(tiles, new int2(0, 0), DefaultMapSize);
            Assert.IsFalse(result);
        }

        [Test]
        public void IsOccupied_OccupiedTile_ReturnsTrue()
        {
            var tiles = CreateDefaultTiles();
            var index = TilemapHelper.CoordToIndex(new int2(5, 5), DefaultMapSize);
            var tile = tiles[index];
            tile.OccupyingEntity = new Entity { Index = 1, Version = 1 };
            tiles[index] = tile;

            var result = TilemapHelper.IsOccupied(tiles, new int2(5, 5), DefaultMapSize);
            Assert.IsTrue(result);
        }

        [Test]
        public void IsOccupied_OutOfBounds_ReturnsFalse()
        {
            var tiles = CreateDefaultTiles();
            var result = TilemapHelper.IsOccupied(tiles, new int2(-1, 0), DefaultMapSize);
            Assert.IsFalse(result);
        }

        #endregion

        #region GetResourceType

        [Test]
        public void GetResourceType_IronOreTile_ReturnsIronOre()
        {
            var tiles = CreateDefaultTiles();
            var index = TilemapHelper.CoordToIndex(new int2(10, 10), DefaultMapSize);
            var tile = tiles[index];
            tile.Resource = ResourceType.IronOre;
            tiles[index] = tile;

            var result = TilemapHelper.GetResourceType(tiles, new int2(10, 10), DefaultMapSize);
            Assert.AreEqual(ResourceType.IronOre, result);
        }

        [Test]
        public void GetResourceType_EmptyTile_ReturnsNone()
        {
            var tiles = CreateDefaultTiles();
            var result = TilemapHelper.GetResourceType(tiles, new int2(0, 0), DefaultMapSize);
            Assert.AreEqual(ResourceType.None, result);
        }

        [Test]
        public void GetResourceType_OutOfBounds_ReturnsNone()
        {
            var tiles = CreateDefaultTiles();
            var result = TilemapHelper.GetResourceType(tiles, new int2(100, 100), DefaultMapSize);
            Assert.AreEqual(ResourceType.None, result);
        }

        #endregion

        #region IsAreaFree

        [Test]
        public void IsAreaFree_AllEmpty_ReturnsTrue()
        {
            var tiles = CreateDefaultTiles();
            var result = TilemapHelper.IsAreaFree(tiles, new int2(0, 0), new int2(2, 2), DefaultMapSize);
            Assert.IsTrue(result);
        }

        [Test]
        public void IsAreaFree_PartiallyOccupied_ReturnsFalse()
        {
            var tiles = CreateDefaultTiles();
            var index = TilemapHelper.CoordToIndex(new int2(1, 1), DefaultMapSize);
            var tile = tiles[index];
            tile.OccupyingEntity = new Entity { Index = 1, Version = 1 };
            tiles[index] = tile;

            var result = TilemapHelper.IsAreaFree(tiles, new int2(0, 0), new int2(2, 2), DefaultMapSize);
            Assert.IsFalse(result);
        }

        [Test]
        public void IsAreaFree_ExceedsBounds_ReturnsFalse()
        {
            var tiles = CreateDefaultTiles();
            var result = TilemapHelper.IsAreaFree(tiles, new int2(63, 63), new int2(2, 2), DefaultMapSize);
            Assert.IsFalse(result);
        }

        #endregion

        #region TrySetOccupant

        [Test]
        public void TrySetOccupant_ValidCoord_ReturnsTrueAndUpdatesEntity()
        {
            var tiles = CreateDefaultTiles();
            var entity = new Entity { Index = 42, Version = 1 };

            var result = TilemapHelper.TrySetOccupant(tiles, new int2(5, 5), DefaultMapSize, entity);

            Assert.IsTrue(result);
            var index = TilemapHelper.CoordToIndex(new int2(5, 5), DefaultMapSize);
            Assert.AreEqual(entity, tiles[index].OccupyingEntity);
        }

        [Test]
        public void TrySetOccupant_OutOfBounds_ReturnsFalse()
        {
            var tiles = CreateDefaultTiles();
            var entity = new Entity { Index = 42, Version = 1 };

            var result = TilemapHelper.TrySetOccupant(tiles, new int2(-1, 0), DefaultMapSize, entity);

            Assert.IsFalse(result);
        }

        #endregion

        #region TryClearOccupant

        [Test]
        public void TryClearOccupant_OccupiedTile_ReturnsTrueAndClearsEntity()
        {
            var tiles = CreateDefaultTiles();
            var index = TilemapHelper.CoordToIndex(new int2(5, 5), DefaultMapSize);
            var tile = tiles[index];
            tile.OccupyingEntity = new Entity { Index = 1, Version = 1 };
            tiles[index] = tile;

            var result = TilemapHelper.TryClearOccupant(tiles, new int2(5, 5), DefaultMapSize);

            Assert.IsTrue(result);
            Assert.AreEqual(Entity.Null, tiles[index].OccupyingEntity);
        }

        [Test]
        public void TryClearOccupant_OutOfBounds_ReturnsFalse()
        {
            var tiles = CreateDefaultTiles();

            var result = TilemapHelper.TryClearOccupant(tiles, new int2(-1, 0), DefaultMapSize);

            Assert.IsFalse(result);
        }

        #endregion

        #region Helpers

        private NativeArray<TileData> CreateDefaultTiles()
        {
            var tiles = new NativeArray<TileData>(
                DefaultMapSize.x * DefaultMapSize.y,
                Allocator.Temp);
            return tiles;
        }

        #endregion
    }
}
