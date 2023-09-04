class Alena:
    uzel_1 = 200
    uzel_2 = 500
    uzel_3 = 300


class SF:
    ...

class Pts_Core:
    offset_aluminiy = 50
    offset_triangles = 500
class Pts_Ceiling:
    offset = Alena.uzel_2


class Facade_Glazing:
    offset = Alena.uzel_1


class Facade_Pilons:
    offset = Alena.uzel_1


class Podshivka:
    offset = Alena.uzel_3



class Core(Pts_Core):
    ...


class Ceiling(Pts_Ceiling):
    ...


class L2(Ceiling):
    ...


class Niche_W1W4(Ceiling, Core):
    ...


class Niche_L2_W1W4(L2, Niche_W1W4):
    ...


class Pilons_L2(L2, Facade_Pilons):
    ...


class Podshivka_L2(L2, Podshivka):
    ...


class Glazing_L2(L2, Facade_Glazing):
    ...
