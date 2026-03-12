using Unity.Entities;

namespace MadFactory.Core
{
    public struct TileData
    {
        public TerrainType Terrain;
        public ResourceType Resource;
        public Entity OccupyingEntity;
    }
}
