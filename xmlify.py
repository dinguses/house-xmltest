#!/usr/bin/env python3.6
# pylint: skip-file
import attr
from lxml import etree
from lxml.builder import E
import typing
from typing import Iterable, Optional, Callable, List
import itertools
import functools
import argparse
import sys

# TODO: support pure bi-directionality
# TODO: check that the name / index dichotomy is handled

use_tag_name = True

Lookup = Callable[[etree._Element], Optional[str]]


def attr_lookup(name: str) -> Lookup:
    return lambda x: x.get(name)


def elt_lookup(name: str) -> Lookup:
    return lambda x: x.findtext(name)


def attr_elt(name: str) -> (Lookup, Lookup):
    return (attr_lookup(name), elt_lookup(name))


def self_lookup(elt) -> str:
    return elt.text


def do_lookup(elt: etree._Element, *lookups: Iterable[Lookup]) -> Optional[str]:
    return next((x for x in (lookup(elt) for lookup in lookups) if x is not None), None)


def do_int_lookup(elt, *lookups):
    for lookup in lookups:
        try:
            return int(lookup(elt))
        except TypeError:
            pass

    return None


@attr.s
class NameSpec:
    id = attr.ib(default=None)
    name = attr.ib(default=None)

    _sourceline = attr.ib(default=None)

    @classmethod
    def typename(cls):
        return cls.__name__[:-4].lower()

    _namesearch = lambda: (attr_lookup("name"), elt_lookup("name"))
    _idsearch = lambda: (attr_lookup("id"), elt_lookup(
        "id"), attr_lookup("index"), elt_lookup("index"))

    def intname(self):
        try:
            int(self.name)
        except TypeError:
            return False
        except ValueError:
            return False
        
        return True

    def _invalid(self):
        raise ValueError(f"{self.__class__.__name__} from {self._sourceline} is missing a name AND id")

    def __str__(self):
        if self.name is not None:
            return self.name
        elif self.id is not None:
            return str(self.id)
        else:
            self._invalid()
    
    def to_xattr(self) -> (str, str):
        if self.name is not None:
            return ("name", self.name)
        elif self.id is not None:
            return ("id", str(self.id))
        else:
            self._invalid()

    #def to_xelt(self, type_name: Optional[str] = None) -> etree._Element:
    #    if type_name is None and ' ' not in self.name and use_tag_name:
    #        return etree.Element(self.name)
    #    else:
    #        return etree.Element(type_name, name=self.name)

    @classmethod
    def from_xelt(cls, elt: etree._Element, *, idsearch=None, namesearch=None):
        id = do_int_lookup(elt, *(idsearch or cls._idsearch()))
        name = do_lookup(elt, *(namesearch or cls._namesearch()))

        return cls(id, name, elt.sourceline)


class CustomSpec(NameSpec):
    @classmethod
    def _namesearch(cls):
        return (attr_lookup(cls.typename()), elt_lookup(cls.typename()))

    @classmethod
    def _idsearch(cls):
        return (attr_lookup(cls.typename()), elt_lookup(cls.typename()))

class ItemSpec(CustomSpec):
    pass


class StateSpec(CustomSpec):
    pass


class RoomSpec(CustomSpec):
    @classmethod
    def _idsearch(cls):
        return [self_lookup]

    def to_xelt(self):
        if use_tag_name and self.name is not None and ' ' not in self.name:
            return etree.Element(self.name)

        attrs = dict([self.to_xattr()])

        return E.room(**attrs)


@attr.s
class ConditionSpec:
    item = attr.ib()
    state = attr.ib()

    @classmethod
    def from_xelt(cls, elt):
        item = ItemSpec.from_xelt(elt)
        state = StateSpec.from_xelt(elt, idsearch=[attr_lookup(
            "state"), attr_lookup("itemstate"), elt_lookup("itemstate")])
        return cls(item, state)

    def to_xelt(self, type_name="prereq"):
        return etree.Element(type_name, item=str(self.item), state=str(self.state))


@attr.s
class State:
    name = attr.ib()
    image = attr.ib()
    description = attr.ib()
    conditions = attr.ib()
    get = attr.ib()
    gettable = attr.ib()

    @classmethod
    def from_xelt(cls, elt: etree._Element, index: Optional[int] = None):
        name = NameSpec.from_xelt(elt)
        if name.id is None:
            name.id = index

        image = attr_lookup("image")(elt)
        description = elt_lookup("description")(elt)

        prereqs = elt.find('prerequisites')
        actions = elt.find('actions')

        if prereqs is not None and actions is not None:
            raise ValueError(
                f"prereqs and actions both exist for elt at {elt.sourceline}")  

        if prereqs is not None:
            conditions = prereqs
        elif actions is not None:
            conditions = actions
        else:
            raise ValueError(f"both prereqs and actions are missing at {elt.sourceline}")
            

        conditions = [ConditionSpec.from_xelt(x) for x in conditions]

        get = elt_lookup("get")(elt)
        gettable = do_lookup(elt, *attr_elt("gettable"))
        if gettable is not None:
            gettable = bool(gettable)

        return cls(name, image, description, conditions, get, gettable)

    def to_xelt(self):
        if use_tag_name and self.name.name is not None and ' ' not in self.name.name:
            x = etree.Element(self.name)
        else:
            k, v = self.name.to_xattr()
            x = E.state()
            x.set(k, v)

        kwargs = dict(image=(self.image if self.image is not None else ""))
        elts = [E.description(self.description)]

        if self.gettable is not None:
            kwargs.update(gettable=str(self.gettable))

        if self.get is not None:
            elts += E.get(self.get)

        elts += E.conditions(*[x.to_xelt() for x in self.conditions])

        x.extend(elts)
        x.attrib.update(kwargs)
        return x


@attr.s
class Item:
    name = attr.ib()
    states = attr.ib()

    _sourceline = attr.ib(default=None)

    @classmethod
    def from_xelt(cls, elt, index=None):
        name = NameSpec.from_xelt(elt)
        if name.id is None:
            # TODO: keep track of this
            name.id = index

        states = [State.from_xelt(x, idx)
                  for idx, x in enumerate(elt.find('states'))]

        return cls(name, states, elt.sourceline)

    def to_xelt(self):
        if use_tag_name and not self.name.intname() and ' ' not in self.name.name:
            x = etree.Element(self.name.name)
        else:
            k, v = self.name.to_xattr()
            x = E.item()
            x.set(k, v)

        x.append(E.states(*[x.to_xelt() for x in self.states]))
        return x


@attr.s
class Room:
    name = attr.ib()
    adjacent_rooms = attr.ib()
    states = attr.ib()
    items = attr.ib()

    @classmethod
    def from_xelt(cls, elt: etree._Element):
        name = NameSpec.from_xelt(elt)
        adjs = [RoomSpec.from_xelt(x)
                for x in elt.find("adjacentrooms")]
        states = [State.from_xelt(x, idx)
                  for idx, x in enumerate(elt.find("states"))]
        items = [Item.from_xelt(x, idx)
                 for idx, x in enumerate(elt.find("items"))]
        return cls(name, adjs, states, items)

    def to_xelt(self):
        name = str(self.name)
        if use_tag_name and ' ' not in name:
            x = etree.Element(name)
        else:
            x = E.room(name=name)
        
        x.extend([
            E.adjacentrooms(*[x.to_xelt() for x in self.adjacent_rooms]),
            E.states(*[x.to_xelt() for x in self.states]),
            E.items(*[x.to_xelt() for x in self.items])
        ])

        return x

@attr.s
class SpecialResponse:
    item = attr.ib()
    image = attr.ib()
    command = attr.ib()
    response = attr.ib()
    item_state = attr.ib()
    actions = attr.ib()

    @classmethod
    def from_xelt(cls, elt):
        item_index = do_int_lookup(elt, elt_lookup("itemindex"))

        if item_index is not None:
            item = ItemSpec(id=item_index)
        else:
            item = ItemSpec.from_xelt(elt)

        image = do_lookup(elt, *attr_elt("image"))

        command = do_lookup(elt, *attr_elt("command"))

        response = elt_lookup("reponse")(elt)

        statesearch = (attr_lookup("state"), elt_lookup("state"),
                       attr_lookup("itemstate"), elt_lookup("itemstate"))
        item_state = StateSpec.from_xelt(elt, idsearch=statesearch)

        actions = [ConditionSpec.from_xelt(x) for x in elt.find("actions")]

        return cls(item, image, command, response, item_state, actions)

    def to_xelt(self):
        response =  E.response()
        if self.response is not None:
            response.text = self.response
        return E.specialresponse(
            response,
            E.actions(*[x.to_xelt() for x in self.actions]),

            item=str(self.item),
            state=str(self.item_state),
            image=self.image,
            command=self.command
        )

@attr.s
class House:
    rooms = attr.ib()
    special_responses = attr.ib()

    @classmethod
    def from_xelt(cls, elt):
        return cls(
            [Room.from_xelt(x) for x in elt.find('rooms')],
            [SpecialResponse.from_xelt(x) for x in elt.find("specialresponses")]
        )

    def to_xelt(self):
        return E.house(
            E.rooms(*[x.to_xelt() for x in self.rooms]),
            E.specialresponses(*[x.to_xelt() for x in self.special_responses])
        )



def minify(instr, pretty=True) -> (int, str, int):
    sourcelen = len(str(instr, encoding="UTF-8").split('\n'))
    house = House.from_xelt(etree.fromstring(instr))
    xml = house.to_xelt()
    out = etree.tostring(xml, pretty_print=pretty)
    out = str(out, encoding="UTF-8")
    outlen = len(out.split('\n'))
    return sourcelen, out, outlen
    

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("infile", type=argparse.FileType('rb'), default='-')

    args = parser.parse_args()

    sourcelen, out, outlen = minify(args.infile.read())
    print(f"Input length: {sourcelen} lines\nOutput length: {outlen} lines", file=sys.stderr)
    print(out)
