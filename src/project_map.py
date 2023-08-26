from mmcore.base.params import BufferNode, Node, Graph
from pyvis.network import Network

# Исходная геометрия
pts_core = Node(uuid="pts_core")
pts_ceiling = Node(uuid="pts_ceiling")
facade_glazing = Node(uuid="facade_glazing")
facade_pilons = Node(uuid="facade_pilon")
podshivka = Node(uuid="podshivka")

# Перестроенные точки
core = Node(uuid='core', pts_core=pts_core)
ceiling = Node(uuid='ceiling', pts_ceiling=pts_ceiling)

# Основные сфоритрованные нами объекты
l2 = Node(uuid="l2", ceiling=ceiling)
nicheW1W4 = Node(uuid="nicheW1W4", ceiling=ceiling, core=core)


# Контуры
niche_L2_W1W4 = Node(uuid="nicheL2_W1W4", ceiling=l2, niche=nicheW1W4)
pilons_L2 = Node(uuid="pilons_L2", ceiling=l2, facade_pilons=facade_pilons)
podshivka_L2 = Node(uuid="podshivka_L2", ceiling=l2, podshivka=podshivka)
glazing_L2 = Node(uuid="glazing_L2", ceiling=l2, glazing=facade_glazing)







nt = Network('1500px', '1500px')
nt.toggle_physics(True)
gr = l2.graph.to_nx()
nt.from_nx(gr)
nt.write_html("/Users/sofya/PycharmProjects/grid/src/lib/sf.html")