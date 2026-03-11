using Unity.Entities;
using Unity.Mathematics;

namespace MadFactory.ECS
{
    public struct GridPosition : IComponentData
    {
        public int2 Value;
    }
}
