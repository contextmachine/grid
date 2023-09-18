import dataclasses
import gzip
import json
import time
from json import JSONEncoder

import numpy as np
import shapely
from mmcore.geom.parametric import PlaneLinear, algorithms


def split3d(poly3, plane):
    pls = []
    if isinstance(poly3, shapely.MultiPolygon):
        for poly in poly3.geoms:
            pts = []
            for pt in list(poly.boundary.coords):
                real_pt = algorithms.ray_plane_intersection(np.array(pt), np.array([0.0, 0.0, 1.0]), plane)
                pts.append(real_pt.tolist())
            pls.append(pts)
    else:
        pts = []
        for pt in list(poly3.boundary.coords):
            real_pt = algorithms.ray_plane_intersection(np.array(pt), np.array([0.0, 0.0, 1.0]), plane)
            pts.append(real_pt.tolist())
        pls.append(pts)
    return pls


class InitialPanel:
    def __init__(self, points, cont_plane=None, name='test'):
        super().__init__()
        self.points = points
        self.poly = shapely.Polygon(points)
        self.plane = algorithms.normal_plane_from_triangle(np.array(points))
        self.name = name
        self.cont_plane = cont_plane

        if self.cont_plane is None:
            self.transformed_points = self.points
        else:
            self.transformed_points = [cont_plane.point_at(pt).tolist() for pt in self.points]

        self.center = algorithms.centroid(np.array(self.transformed_points)).tolist()

    def split(self, cont):

        poly1 = self.poly

        if poly1.intersects(cont):
            if poly1.within(cont):
                # print("inside")

                return [self.transformed_points], 0


            else:

                # print("intersects")
                poly3 = poly1.intersection(cont)
                res=split3d(poly3, self.plane)
                if self.cont_plane is not None:
                    return [[self.cont_plane.point_at(pt).tolist() for pt in part]for part in res], 1
                else:
                    return res,1
        else:
            # print("outside")
            return [self.transformed_points], 2
    def __hash__(self):
        return hash(repr(self.points))

@dataclasses.dataclass
class CutPanelsResult:
    mask: list[int]
    shapes: list
    centers: list[str]
    names: list[list[float]]


def solve_cut(pans: list[InitialPanel], contour) -> CutPanelsResult:
    mask = []
    shapes = []
    centers = []
    names = []
    for i, pnl in enumerate(pans):
        centers.append(pnl.center)
        names.append(pnl.name)
        _panel, _mask = pnl.split(contour)

        mask.append(_mask)
        shapes.append(_panel)
    return CutPanelsResult(**{
        "centers": centers,
        "shapes": shapes,
        "mask": mask,
        "names": names
    })

class Poly:
    def __init__(self, bounds, holes=None, plane=None):
        super().__init__()

        self.plane=plane
        if self.plane is None:
            self.bounds = bounds
            self.holes = holes

        else:
            self.bounds = [self.plane.in_plane_coords(pt) for pt in bounds]
            if holes is not None:
                self.holes = [[self.plane.in_plane_coords(pt) for pt in hole] for hole in holes]
            else:
                self.holes=holes
        self.poly = shapely.Polygon(self.bounds)
        if self.holes is not None:
            self.poly = self.poly.difference([shapely.Polygon(hole) for hole in self.holes])[0]



class Contour:
    def __init__(self, shapes, plane=None):
        polys=shapes
        self.plane=plane
        if isinstance(polys[0], Poly):
            if len(polys)==1:
                self.poly=polys[0].poly
            else:
                self.poly = shapely.multipolygons([pol.poly for pol in polys])

        else:
            if len(polys)==1:

                self.poly=Poly(**polys[0], plane=self.plane).poly
            else:
                self.poly = shapely.multipolygons([Poly(**pol, plane=self.plane).poly for pol in polys])

    def __eq__(self, other):

        return self.poly==other.poly

class Model:
    def __init__(self, initial, contour):
        self.initial_panels = initial
        self.contour = contour
        #self.prev= self.initial_panels, self.contour.poly
        self.cache=dict()

    def update_contour(self, contour):
        self.contour = contour


    @property
    def cut_result(self):
        hs=hash( self.contour.poly)
        if hs not in self.cache:

            self.cache[hs]=solve_cut(self.initial_panels, self.contour.poly)
        return self.cache[hs]

w1,w2,w3,w4=[PlaneLinear(origin=(-213065.70753364256, -35086.37129244862, -2050.000000000022), normal=np.array([-0.97437049,  0.22494923,  0.        ]), xaxis=np.array([0., 0., 1.]), yaxis=np.array([ 0.22494923,  0.97437049, -0.        ])),
PlaneLinear(origin=(-208372.86174235368, -14759.249075588159, -2050.000000000022), normal=np.array([-0.03335027,  0.99944373,  0.        ]), xaxis=np.array([0., 0., 1.]), yaxis=np.array([ 0.99944373,  0.03335027, -0.        ])),

PlaneLinear(origin=(-187527.0641906429, -14063.649195563296, -2050.000000000022), normal=np.array([ 0.99741995,  0.07178751, -0.        ]), xaxis=np.array([0., 0., 1.]), yaxis=np.array([ 0.07178751, -0.99741995,  0.        ])),

PlaneLinear(origin=(-186302.55593254333, -31077.040223981054, -2050.000000000022), normal=np.array([ 0.14815463, -0.98896421,  0.        ]), xaxis=np.array([0., 0., 1.]), yaxis=np.array([-0.98896421, -0.14815463,  0.        ]))]



#test_contour=Contour(
#    [
#        [(-219752.98045902306, -38091.117611140740, 0.0),
#      (-153162.02100481867, -28119.531737697045, 0.0),
#      (-154151.72703612328, -17729.914450278113, 0.0),
#      (-164042.52282802979, -8332.5975232808487, 0.0),
#      (-211925.78905763017, -9999.8881830768441, 0.0)],
#     [
#         [(-213587.65793108218, -35569.027152161463, 0.0),
#          (-185876.99912176811, -31417.752035245710, 0.0),
#          (-187155.72663277033, -13651.035461818239, 0.0),
#          (-208693.45508905061, -14369.724266745601, 0.0)]]])

def model_from_json(path='/Users/andrewastakhov/PycharmProjects/v2/swdata/SW_triangles.gz', cont=None):
    with  gzip.open(path, "rb") as f:
        import json
        tri = json.loads(f.read().decode())
    return Model([InitialPanel(tr, cont_plane=cont.plane) for tr in tri], cont)
class MasterModel:
    models=dict()
    def build(self, name, shapes, contour, plane):

        _plane = PlaneLinear(**plane) if plane else None
        cont=Contour(contour['shapes'], plane=_plane)
        self.models[name]=Model([InitialPanel(tr, cont_plane=cont.plane) for tr in shapes], cont)
    def __init__(self):...

def build(panels=None, contour=None):
    _plane = PlaneLinear(**contour.get('plane') ) if contour.get('plane') else None
    cont = Contour(contour['shapes'], plane=_plane)
    return Model([InitialPanel(tr, cont_plane=cont.plane) for tr in panels], cont)

def test_model():
    s=time.time()
    model=model_from_json()

    mnt,secs=divmod(time.time()-s,60)
    print(f"creating model with {len(model.initial_panels)} items: {mnt} min {secs} secs")
    s=time.time()
    cut=model.cut_result
    mnt, secs = divmod(time.time() - s, 60)
    print(f"cut model: {mnt} min {secs} secs")
    return model,cut

class MyJSONEncoder(JSONEncoder):
    def default(self, o):
        if isinstance(o,np.ndarray):
            return o.tolist()
        else:
            return super().default(o)


def test2(path='/Users/andrewastakhov/PycharmProjects/v2/swdata/walls/SW_triangles_by_walls_dict.json', path2='/Users/andrewastakhov/PycharmProjects/grid/src/tests/conts.json',target='/Users/andrewastakhov/PycharmProjects/grid/src/tests/test2.json'):
    models=dict()
    cuts=dict()
    with open(path) as f:
        panels=json.load(f)
    with open(path2) as f2:
        cases=json.load(f2)
    for name, case in cases.items():
        s = time.time()
        m=    build(panels=panels[name], contour=case)
        mnt, secs = divmod(time.time() - s, 60)
        models[name] =  m
        print(f"creating model '{name}' with {len(m.initial_panels)} items: {mnt} min {secs} secs")
    for k, model in models.items():
        s = time.time()
        cuts[k] = model.cut_result
        mnt, secs = divmod(time.time() - s, 60)
        print(f"cut model : {mnt} min {secs} secs")
    with open('/Users/andrewastakhov/PycharmProjects/grid/src/tests/test2.json', 'w') as f3:
        json.dump([dataclasses.asdict(cut) for cut in cuts.values()], f3)

    return models,cuts

