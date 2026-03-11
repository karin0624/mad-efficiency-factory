using Unity.Entities;
using Unity.Mathematics;

namespace MadFactory.ECS
{
    public struct GridSize : IComponentData
    {
        public int2 Value;
    }
}
