using System;
using System.Collections.Generic;
using System.Xml.Linq;
using System.Linq;
using System.IO;
using X = XElementExtensions;

struct ValidationIssue {
    public int lineNum;
    public int linePos;
    public string issue;
}

/// <summary>
/// Something that was originally identified by an ID, but should have a name instead.
/// Things that have names themselves should use this. If you're attemtping to reference
/// something *else* by name or ID, use one of its subclasses.
/// </summary>
class NameSpec
{
    public int? id;
    public string name;

    public XElement elt;

    private static readonly string[] idNames = new string[] { "id", "index" };

    public static implicit operator XAttribute(NameSpec self)
    {
        if (self.name == null)
        {
            return new XAttribute("id", self.id);
        }
        else
        {
            return new XAttribute("name", self.name);
        }
    }

    public static T Parse<T>(XElement elt, string[] idnames, string[] namenames) where T : NameSpec, new()
    {
        var idlookups = idnames.Select(X.Attr).Concat(idnames.Select(X.Elt)).ToArray();
        var namelookups = namenames.Select(X.Attr).Concat(namenames.Select(X.Elt)).ToArray();
        return new T
        {
            id = elt.GetFirst(idlookups)?.ParseInt(),
            name = elt.GetFirst(namelookups)
        };
    }

    public static T Parse<T>(XElement elt, string idname, string namename) where T : NameSpec, new()
    {
        return new T
        {
            id = elt.GetFirst(X.Attr(idname), X.Elt(idname))?.ParseInt(),
            name = elt.GetFirst(X.Attr(namename), X.Elt(namename))
        };
    }

    public static T Parse<T>(XElement elt, params Func<XElement, string>[] checkers) where T : NameSpec, new()
    {
        var val = elt.GetFirst(checkers);
        return new T
        {
            id = val?.ParseInt(),
            name = val
        };
    }

    public static NameSpec Parse(XElement elt)
    {
        return Parse<NameSpec>(elt, idNames, nameNames);
    }
}


class ItemSpec : NameSpec
{
    public static readonly string attrname = "item";
    public static implicit operator XAttribute(ItemSpec self)
    {
        return new XAttribute("item", self.name);
    }

    public static new ItemSpec Parse(XElement elt)
    {
        return Parse<ItemSpec>(elt, attrname, attrname);
    }
}

class StateSpec : NameSpec
{
    public static implicit operator XAttribute(StateSpec self)
    {
        return new XAttribute("state", self.name);
    }
    public static new StateSpec Parse(XElement elt)
    {
        return Parse<StateSpec>(elt, "state", "state");
    }
}

class RoomSpec : NameSpec
{
    public static implicit operator XAttribute(RoomSpec self)
    {
        return new XAttribute("room", self.name);
    }
    public static implicit operator XElement(RoomSpec self)
    {
        return new XElement("room", (self.name == null) ? new XAttribute("id", self.id) : new XAttribute("name", self.name));
    }
    public static new RoomSpec Parse(XElement elt)
    {
        return Parse<RoomSpec>(elt, "room", "room");
    }
}


class Room
{
    public NameSpec name;
    public List<RoomSpec> adjacentRooms;
    public List<RoomState> states;
    public List<Item> items;

    public static implicit operator XElement(Room self)
    {
        Console.WriteLine("Casting Room to XElement");
        var firstAdjRoom = (XElement)self.adjacentRooms[0];
        return new XElement("room", (XAttribute)self.name,
            new XElement("adjacentRooms", self.adjacentRooms.Cast<XElement>()),
            new XElement("states", self.states.Cast<XElement>()),
            new XElement("items", self.items.Cast<XElement>())
        );
    }

    public static Room Parse(XElement elt)
    {
        return new Room
        {
            name = NameSpec.Parse(elt),
            adjacentRooms = elt.Element("adjacentrooms").Elements().Select(RoomSpec.Parse).ToList(),
            states = elt.Element("states").Elements().WithIndex((x, y) => RoomState.Parse(y, x)).ToList(),
            items = elt.Element("items").Elements().WithIndex((x, y) => Item.Parse(y, x)).ToList()
        };
    }
}

class ConditionSpec
{
    public ItemSpec item;
    public StateSpec state;

    public static implicit operator XElement(ConditionSpec self)
    {
        return new XElement(null, (XAttribute)self.item, (XAttribute)self.state);
    }

    public static ConditionSpec Parse(XElement elt)
    {
        // TODO: figure out if ints or strings
        return new ConditionSpec
        {
            item = ItemSpec.Parse(elt),
            state = NameSpec.Parse<StateSpec>(elt, X.Attr("itemstate"), X.Elt("itemstate"), X.Attr("state"), X.Elt("state"))
        };
    }
}

static class Extensions
{
    public static IEnumerable<XElement> OfTitle(this IEnumerable<ConditionSpec> self, string typ)
    {
        return self.Cast<XElement>().Select((x => { x.Name = typ; return x; }));
    }

    public static int? ParseInt(this string self)
    {
        int i;
        if (int.TryParse(self, out i))
        {
            return i;
        }

        return null;
    }

    public static IEnumerable<U> WithIndex<T, U>(this IEnumerable<T> self, Func<int, T, U> transformer) {
        int i = 0;
        return self.Select(x => transformer.Invoke(i++, x));
    }
}

class State
{
    public NameSpec name;
    public string image;
    public string description;
    public List<ConditionSpec> conditions;

}

class RoomState : State
{
    public static implicit operator XElement(RoomState self)
    {
        return new XElement("state",
            (XAttribute)self.name,
            new XAttribute("image", self.image),
            new XElement("description", self.description),
            new XElement("prerequisites", self.conditions.OfTitle("prerequisite"))
        );
    }

    public static RoomState Parse(XElement elt, int? index)
    {
        var name = NameSpec.Parse(elt);
        name.id = index;

        return new RoomState
        {
            name = name,
            image = elt.GetFirst(X.Attr("image"), X.Elt("image")),
            description = elt.Elt("description"),
            conditions = elt.Element("prerequisites").Elements().Select(ConditionSpec.Parse).ToList()
        };
    }
}

class ItemState : State
{
    public string get;
    public int? gettable;

    public static implicit operator XElement(ItemState self)
    {
        return new XElement("state",
            (XAttribute)self.name,
            new XAttribute("image", self.image),
            (self.gettable != null) ? new XAttribute("gettable", self.gettable) : null,
            new XElement("description", self.get),
            new XElement("actions", self.conditions.OfTitle("action"))
        );
    }


    public static ItemState Parse(XElement elt, int? index)
    {
        var name = NameSpec.Parse(elt);
        name.id = index;

        return new ItemState
        {
            name = NameSpec.Parse(elt),
            image = elt.GetFirst(X.Attr("image"), X.Elt("image")),
            description = elt.Elt("description"),
            get = elt.Elt("get"),
            gettable = elt.GetFirst(X.Attr("gettable"), X.Elt("gettable"))?.ParseInt(),
            conditions = elt.Element("actions").Elements().Select(ConditionSpec.Parse).ToList()
        };
    }
}

class Item
{
    public NameSpec name;
    public List<ItemState> states;

    public static implicit operator XElement(Item self)
    {
        return new XElement("item", (XAttribute)self.name, new XElement("states", self.states.Cast<XElement>()));
    }

    public static Item Parse(XElement elt, int? index) {
        var name = NameSpec.Parse(elt);
        if (name.id != null && index != null) name.id = index;

        return new Item {
            name = name,
            states = elt.Element("states").Elements().WithIndex((x, y) => ItemState.Parse(y, x)).ToList()
        };
    }
}

class SpecialResponse
{
    public ItemSpec item;
    public string image;
    public string command;
    public string response;
    public StateSpec itemstate;
    public List<ConditionSpec> actions;

    public static implicit operator XElement(SpecialResponse self)
    {
        return new XElement("specialresponse",
            (XAttribute)self.item,
            new XAttribute("itemstate", self.itemstate.name),
            new XAttribute("image", self.image),
            new XAttribute("command", self.command),
            new XElement("response", self.response),
            new XElement("actions", self.actions.OfTitle("action"))
        );
    }

    public static SpecialResponse Parse(XElement elt) {
        return new SpecialResponse {
            item = new ItemSpec { id = elt.Elt("itemindex")?.ParseInt() },
            image = elt.Elt("image"),
            command = elt.Elt("command"),
            response = elt.Elt("response"),
            itemstate = new StateSpec { id = elt.Elt("itemstate")?.ParseInt() },
            actions = elt.Element("actions").Elements().Select(ConditionSpec.Parse).ToList()
        };
    }
}

class House {
    public List<Room> rooms;
    public List<SpecialResponse> specialresponses;

    public static House Parse(XElement elt) {
        return new House {
            rooms = elt.Element("rooms").Elements().Select(Room.Parse).ToList(),
            specialresponses = elt.Element("specialresponses").Elements().Select(SpecialResponse.Parse).ToList()
        };
    }

    public static implicit operator XElement(House self)
    {
        Console.WriteLine("Casting House to XElement");
        var firstRoom = (XElement)self.rooms[0];
        Console.WriteLine("Casted single room");
        var rooms = self.rooms.Cast<XElement>();
        return new XElement("house",
            new XElement("rooms", rooms),
            new XElement("specialresponses", self.specialresponses)
        );
    }
}

public class Program
{
    public static void Main(string[] args)
    {
        XElement houseXML = XElement.Load("house.xml", LoadOptions.SetLineInfo);
        House house = House.Parse(houseXML);
        XElement reducedXML = (XElement)house;

        using (var writer = new StreamWriter(File.OpenWrite("reduced_house.xml"))) {
            reducedXML.Save(writer);
        }
    }
}