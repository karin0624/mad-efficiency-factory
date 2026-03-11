using Unity.Collections;
using Unity.Entities;
using Unity.Mathematics;
using MadFactory.Core;

namespace MadFactory.ECS
{
    public struct TilemapSingleton : IComponentData
    {
        public int2 MapSize;
        public NativeArray<TileData> Tiles;
    }
}
