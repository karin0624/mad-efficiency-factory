using Unity.Collections;
using Unity.Entities;
using Unity.Mathematics;

namespace MadFactory.Core
{
    public static class TilemapHelper
    {
        public static int CoordToIndex(int2 coord, int2 mapSize)
        {
            return coord.y * mapSize.x + coord.x;
        }

        public static bool IsInBounds(int2 coord, int2 mapSize)
        {
            return coord.x >= 0 && coord.y >= 0 &&
                   coord.x < mapSize.x && coord.y < mapSize.y;
        }

        public static bool IsOccupied(NativeArray<TileData> tiles, int2 coord, int2 mapSize)
        {
            if (!IsInBounds(coord, mapSize))
                return false;

            var index = CoordToIndex(coord, mapSize);
            return tiles[index].OccupyingEntity != Entity.Null;
        }

        public static ResourceType GetResourceType(NativeArray<TileData> tiles, int2 coord, int2 mapSize)
        {
            if (!IsInBounds(coord, mapSize))
                return ResourceType.None;

            var index = CoordToIndex(coord, mapSize);
            return tiles[index].Resource;
        }

        public static bool IsAreaFree(NativeArray<TileData> tiles, int2 origin, int2 size, int2 mapSize)
        {
            for (int y = origin.y; y < origin.y + size.y; y++)
            {
                for (int x = origin.x; x < origin.x + size.x; x++)
                {
                    var coord = new int2(x, y);
                    if (!IsInBounds(coord, mapSize))
                        return false;

                    var index = CoordToIndex(coord, mapSize);
                    if (tiles[index].OccupyingEntity != Entity.Null)
                        return false;
                }
            }

            return true;
        }

        public static bool TrySetOccupant(NativeArray<TileData> tiles, int2 coord, int2 mapSize, Entity entity)
        {
            if (!IsInBounds(coord, mapSize))
                return false;

            var index = CoordToIndex(coord, mapSize);
            var tile = tiles[index];
            tile.OccupyingEntity = entity;
            tiles[index] = tile;
            return true;
        }

        public static bool TryClearOccupant(NativeArray<TileData> tiles, int2 coord, int2 mapSize)
        {
            if (!IsInBounds(coord, mapSize))
                return false;

            var index = CoordToIndex(coord, mapSize);
            var tile = tiles[index];
            tile.OccupyingEntity = Entity.Null;
            tiles[index] = tile;
            return true;
        }
    }
}
