"""Grasshopper Script"""
# ! python 3

import Rhino.Geometry as rg
import ghpythonlib.treehelpers as th
import json
import numpy as np
class Triang:
    type_tag = 'Abstract'
    geom = A
    arch_type = "A"
    eng_type = 0
    pair_index = 1
    panel_type = "standard"
    padding=0
    _pair_name="0_0"
    def __init__(self, plane, pos=None):
        self.next = None
        self.prev = None
        self.pos = pos

        self.plane = plane

        self.shape = self.geom.Duplicate()
        self.shape.Transform(self.transformation)

    @property
    def transformation(self):
        tr = rg.Transform.PlaneToPlane(rg.Plane.WorldXY, self.plane)
        return tr

    @property
    def prev(self):
        return self._prev

    @prev.setter
    def prev(self, s):
        self._prev = s
    def points(self):
        return [[item.X,item.Y,item.Z] for item in self.shape.ToPolyline()][:-1]
    @property
    def pair_name(self):
        return self._pair_name
    def todict(self):
        pts=self.points()
        return dict(
            arch_type=self.arch_type,
            eng_type=self.eng_type,
            pair_index=self.pair_index,
            pair_name=self.pair_name,
            panel_type=self.panel_type,
            padding=self.padding,
            center=np.mean(np.array(pts),axis=0).tolist(),
            points=pts



        )
    def __repr__(self):
        return f'{json.dumps(self.todict(),indent=2)}'
class Base_cl(Triang):
    geom = Base
    left = 400 / 2
    padding = 0
    type_tag = 'Base'
    pair_index = 1
    panel_type = "standard"
    def __init__(self, plane=None, pos=None, leftover=None, spec=None):
        super().__init__(plane, pos=pos)

        if leftover >= 300:
            self.next = BaseM_cl
        else:
            if spec is None:
                self.next = AM_cl
            else:
                self.next = AM30_cl


class BaseM_cl(Triang):
    geom = Base_M
    left = 400 / 2
    padding = 0
    type_tag = 'BaseM'
    pair_index = 2
    panel_type="standard"
    def __init__(self, plane=None, pos=None, leftover=None, spec=None):
        super().__init__(plane, pos=pos)

        if leftover > 300.0:
            self.next = Base_cl
        else:
            if spec is None:
                self.next = B_cl
            else:
                self.next = B30_cl


class A_cl(Triang):
    geom = A
    left = 228.7
    padding = 28.7
    type_tag = 'A'
    pair_index = 2
    panel_type = "corner"
    def __init__(self, plane=None, pos=None, leftover=None):
        super().__init__(plane, pos=pos)

        self.next = Base_cl
        self.prev = AM_cl


class AM_cl(Triang):
    geom = A_M
    left = 228.7
    type_tag = 'AM'
    pair_index = 2
    panel_type = "corner"
    padding = 28.7
    def __init__(self, plane=None, pos=None, leftover=None):
        super().__init__(plane, pos=pos)

        self.next = A_cl
        self.prev = Base_cl


class A30_cl(Triang):
    geom = A30
    left = 233.1
    type_tag = 'A'
    pair_index = 2
    panel_type = "corner"
    def __init__(self, plane=None, pos=None, leftover=None):
        super().__init__(plane, pos=pos)

        self.next = Base_cl
        self.prev = AM30_cl


class AM30_cl(Triang):
    geom = A_M30
    left = 233.1
    padding = 33.1
    type_tag = 'AM'
    pair_index = 2
    panel_type = "corner"
    def __init__(self, plane=None, pos=None, leftover=None):
        super().__init__(plane, pos=pos)

        self.next = A30_cl
        self.prev = Base_cl


class B30_cl(Triang):
    geom = B30
    left = 233.1
    padding = 33.1
    type_tag = 'B'
    pair_index = 1
    panel_type = "corner"
    def __init__(self, plane=None, pos=None, leftover=None):
        super().__init__(plane, pos=pos)

        self.next = BM_cl
        self.prev = BaseM_cl


class BM30_cl(Triang):
    geom = B_M30
    left = 233.1
    type_tag = 'BM'
    pair_index = 1
    panel_type = "corner"
    def __init__(self, plane=None, pos=None, leftover=None):
        super().__init__(plane, pos=pos)

        self.next = BaseM_cl
        self.prev = B30_cl


class B_cl(Triang):
    geom = B

    left = 228.7
    padding = 28.7
    type_tag = 'B'
    pair_index = 1
    panel_type = "corner"
    def __init__(self, plane=None, pos=None, leftover=None):
        super().__init__(plane, pos=pos)

        self.next = BM_cl
        self.prev = BaseM_cl


class BM_cl(Triang):
    geom = B_M
    left = 228.7
    padding = 28.7
    type_tag = 'BM'
    panel_type="corner"
    pair_index = 1

    def __init__(self, plane=None, pos=None, leftover=None):
        super().__init__(plane, pos=pos)

        self.next = BaseM_cl
        self.prev = B_cl


class Position:
    opt = (A_cl, AM_cl, B_cl, BM_cl, A30_cl, AM30_cl, B30_cl, BM30_cl)

    def __init__(self, surf, start_geom=A30_cl, init_frame=None):
        self.state = 0

        self.surf = surf

        if init_frame is None:
            self.init_frame = [i.FrameAt(0, 0)[1] for i in self.surf]
        else:
            self.init_frame = init_frame

        self.geoms = [[start_geom(self.init_frame[0], pos=0)], [], [], []]

        self.leftover = [i.GetSurfaceSize()[2] for i in self.surf]
        self.origin = [i.Clone() for i in self.init_frame]

    def __call__(self):

        for i in range(4):
            o = 0
            while True:
                if type(self.geoms[self.state][-1]) in self.opt and len(self.geoms[self.state]) > 1:

                    try:
                        prev = self.geoms[self.state][-1].next

                        self.state += 1
                        shape = prev(self.init_frame[self.state], pos=0, leftover=self.leftover[self.state])

                        self.geoms[self.state].append(shape)
                        break

                    except IndexError:

                        break

                prev = self.geoms[self.state][-1]

                self.leftover[self.state] -= prev.left
                o += 1

                self.next()

    def next(self):
        prev = self.geoms[self.state][-1]
        follow = prev.next

        new_frame = self.move_point(prev.left)

        if self.state == 3:
            try:
                shape = follow(new_frame, prev.pos + 1, leftover=self.leftover[self.state], spec=True)
            except:
                shape = follow(new_frame, prev.pos + 1, leftover=self.leftover[self.state])
        else:
            shape = follow(new_frame, prev.pos + 1, leftover=self.leftover[self.state])

        self.geoms[self.state].append(shape)

    def move_point(self, dist):
        frame = self.origin[self.state].Clone()

        vec = self.init_frame[self.state].YAxis

        transform = rg.Transform.Translation(vec * dist)
        frame.Transform(transform)
        self.origin[self.state] = frame

        # return self.surf[self.state].ClosestPoint(point)
        return frame


result = [[], [], [], []]
initial_frame = [i.FrameAt(0, 0)[1] for i in x]

for i in range(35):

    if i % 2 == 0:
        calc = Position(x, start_geom=A30_cl, init_frame=initial_frame)
    else:
        calc = Position(x, start_geom=BM30_cl, init_frame=initial_frame)
    calc()

    for ii, vv in enumerate(result):
        vv.append(calc.geoms[ii])

    tr = rg.Transform.Translation(rg.Vector3d.ZAxis * 600)
    initial_frame = [i.Clone() for i in initial_frame]
    [i.Transform(tr) for i in initial_frame]

for row, value in enumerate(result[0][6:11]):

    plane = value[-1].plane
    new = value[-4].next
    del result[0][6 + row][-1]

    for i in range(21):
        trngl = new(plane, len(result[0][6 + row]) + 1, 500)
        result[0][6 + row].append(trngl)
        new = result[0][6 + row][-1].next

        frame = plane.Clone()
        vec = plane.YAxis
        transform = rg.Transform.Translation(vec * 200)
        frame.Transform(transform)
        plane = frame

shape = []
for wl,r in enumerate(result):
    temp = []
    for i,v in enumerate(r):
        for j,ii in  enumerate(v):

            ii._pair_name=f'{wl}_{i}_{j}'
        row = [ii.shape for ii in v]
        temp.append(row)
    shape.append(temp)

objects = th.list_to_tree(result)
shape = th.list_to_tree(shape)


