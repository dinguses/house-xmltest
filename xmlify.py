#!/usr/bin/env python3
# pylint: skip-file
import attr
from lxml import etree
import typing
from typing import Iterable, Optional, Callable, List
import itertools
import functools
import argparse

# TODO: support pure bi-directionality
# TODO: check that the name / index dichotomy is handled

use_tag_name = True


@attr.s
class ValidationError:
    source = attr.ib()
    issue = attr.ib()


Lookup = Callable[[etree._Element], Optional[str]]


def attr_lookup(name: str) -> Lookup:
    return functools.partialmethod(etree._Element.get, name)


def elt_lookup(name: str) -> Lookup:
    return functools.partialmethod(etree._Element.findtext, name)


def attr_elt(name: str) -> (Lookup, Lookup):
    return (attr_lookup(name), elt_lookup(name))


def do_lookup(elt: etree._Element, *lookups: Iterable[Lookup]) -> Optional[str]:
    return next((x for x in (lookup(elt) for lookup in lookups) if x is not None), None)


def do_int_lookup(elt, *lookups):
    for lookup in lookups:
        try:
            return int(lookup(elt))
        except ValueError:
            pass

    return None


@attr.s
class NameSpec:
    id = attr.ib(default=None)
    name = attr.ib()

    _sourceline = attr.ib(default=None)

    @classmethod
    def name(cls):
        return cls.__name__[:-4].lower()

    _namesearch = lambda: (attr_lookup("name"), elt_lookup("name"))
    _idsearch = lambda: (attr_lookup("id"), elt_lookup(
        "id"), attr_lookup("index"), elt_lookup("index"))

    def __str__(self):
        if self.name is not None:
            return self.name
        elif self.id is not None:
            return str(self.id)
        else:
            raise ValueError()

    def validate(self) -> Iterable[ValidationError]:
        if self.id is None and self.name is None:
            return tuple(ValidationError(self._lineinfo, "Missing either an id or name"))
        return tuple()

    def to_xelt(self, type_name: Optional[str] = None) -> etree._Element:
        if type_name is None:
            return etree.Element(type_name, name=self.name)
        else:
            return etree.Element(self.name)

    @classmethod
    def from_xelt(cls, elt: etree._Element, *, idsearch=None, namesearch=None):
        id = do_int_lookup(elt, *(idsearch or cls._idsearch()))
        name = do_lookup(elt, *(namesearch or cls._namesearch()))
        return cls(id, name, elt.sourceline)


class CustomSpec(NameSpec):

    @classmethod
    def _namesearch(cls):
        return (attr_lookup(cls.name()), elt_lookup(cls.name()))

    @classmethod
    def _idsearch(cls):
        return (attr_lookup(cls.name()), elt_lookup(cls.name()))


class ItemSpec(CustomSpec):
    pass


class StateSpec(CustomSpec):
    pass


class RoomSpec(CustomSpec):
    pass


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
        return etree.Element(type_name, item=self.item, state=self.state)


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

        if prereqs and actions:
            raise ValueError(
                f"prereqs and actions both exist for elt at {elt.sourceline}")

        conditions = [ConditionSpec.from_xelt(x) for x in (prereqs or actions)]

        get = elt_lookup("get")(elt)
        gettable = attr_elt("gettable")(elt)
        if gettable is not None:
            gettable = bool(gettable)

        return cls(name, image, description, conditions, get, gettable)

    def to_xelt(self):
        name = str(self.name)
        name = name if use_tag_name and ' ' not in name else "state"

        kwargs = dict(image=self.image)
        elts = [E.description(self.description)]

        if gettable is not None:
            kwargs.update(gettable=self.gettable)

        if get is not None:
            elts += E.get(self.get)

        elts += E.conditions(*[x.to_xelt() for x in self.conditions])

        x = etree.Element(name, attrib=kwargs)
        x.extend(elts)
        return x


@attr.s
class Item:
    name = attr.ib()
    states = attr.ib()

    @classmethod
    def from_xelt(cls, elt, index=None):
        name = NameSpec.from_xelt(elt)
        if name.id is None:
            # TODO: keep track of this
            name.id = index

        states = [State.from_xelt(x, idx)
                  for idx, x in enumerate(elt.find('states'))]

        return cls(name, states)

    def to_xelt(self):
        name = str(self.name)
        name = name if use_tag_name and ' ' not in name else "item"

        x = etree.Element(name)
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
        adjs = [RoomSpec.from_xelt(x) for x in elt.find("adjacentRooms")]
        states = [RoomState.from_xelt(x, idx)
                  for idx, x in enumerate(elt.find("states"))]
        items = [Item.from_xelt(x, idx)
                 for idx, x in enumerate(elt.find("items"))]
        return cls(name, adjs, states, items)


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
        item_index = do_int_lookups(elt, elt_lookup("itemindex"))

        if item_index is not None:
            item = ItemSpec(id=item_index)
        else:
            item = ItemSpec.from_xelt(elt)

        image = do_lookup(elt, *attr_elt("image"))

        command = do_lookup(elt, *attr_elt("command"))

        response = elt_lookup("reponse")(elt)

        statesearch = (attr_lookup("state"), elt_lookup("state"),
                       attr_lookup("itemstate"), elt_lookup("itemstate"))
        item_state = StateSpec.from_xelt(elt, idsearch=idsearch)

        actions = [ConditionSpec.from_xelt(x) for x in elt.find("actions")]

        return cls(item, image, command, response, statesearch, item_state, actions)

    def to_xelt(self):
        return E.specialresponse(
            E.response(self.response),
            E.actions(*[x.to_xelt() for x in self.actions]),

            item=str(self.item),
            state=str(item_state),
            image=self.image,
            command=self.command
        )

@attr.s
class House:
    rooms = attr.ib()
    special_repsonses = attr.ib()

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


def minify(instr, pretty=True) -> str:
    return etree.tostring(House.from_xelt(etree.fromstring(instr)).to_xelt(), pretty)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("infile", type=argpare.FileType(), default='-')

    args = parser.parse_args()

    print(minify(args.infile.read()))