using System;
using System.Collections.Generic;
using System.Xml.Linq;
using System.Linq;
using X = XElementExtensions;


class NameSpec
{
    public int? id;
    public string name;
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

    public static T Parse<T>(XElement elt) where T : NameSpec, new()
    {
        return new T
        {
            id = int.Parse(elt.GetFirst(X.Attr("id"), X.Attr("index"), X.Elt("id"), X.Elt("index"))),
            name = elt.GetFirst(X.Attr("name"), X.Elt("name"))
        };
    }

    public static NameSpec Parse(XElement elt)
    {
        return Parse<NameSpec>(elt);
    }
}

class ItemSpec : NameSpec
{
    public static implicit operator XAttribute(ItemSpec self)
    {
        return new XAttribute("item", self.name);
    }

    public static new ItemSpec Parse(XElement elt)
    {
        return Parse<ItemSpec>(elt);
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
        return Parse<StateSpec>(elt);
    }
}

class RoomSpec : NameSpec
{
    public static implicit operator XAttribute(RoomSpec self)
    {
        return new XAttribute("room", self.name);
    }
    public static new RoomSpec Parse(XElement elt)
    {
        return Parse<RoomSpec>(elt);
    }
}


class Room
{
    public NameSpec name;
    public List<RoomSpec> adjacentRooms;
    public List<State> states;
    public List<Item> items;

    public static implicit operator XElement(Room self)
    {
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
            name = NameSpec.Parse<NameSpec>(elt),
            adjacentRooms = elt.Element("adjacentrooms").Elements().Select(RoomSpec.Parse).ToList(),
            states = elt.Element("states").Elements().Select(State.Parse),
            items = elt.Element("items").Elements().Select(Item.Parse)
        };
    }
}

class ConditionSpec
{
    public ItemSpec item;
    public StateSpec state;

    public static implicit operator XElement(ConditionSpec self)
    {
        return new XElement(null, (XAttribute)self.item, new XAttribute("itemstate", self.state));
    }

    public static ConditionSpec Parse(XElement elt)
    {
        // TODO: figure out if ints or strings
        var item = elt.GetFirst(x => x.Attr("item"), x => x.Elt("item"));
        int? itemInt = int.Parse(item);
        var state = elt.GetFirst(X.Attr("itemstate"), X.Elt("itemstate"), X.Attr("state"), X.Elt("state"));
        return new ConditionSpec
        {
           
        };
    }
}

static class Extensions
{
    public static IEnumerable<XElement> OfTitle(this IEnumerable<ConditionSpec> self, string typ)
    {
        return self.Cast<XElement>().Select((x => { x.Name = typ; return x; }));
    }
}

abstract class State
{
    public NameSpec name;
    public string image;
    public string description;
    public string get;
    public int gettable;
    public List<ConditionSpec> conditions;
    protected string conditionType;

    public static implicit operator XElement(State self)
    {
        return new XElement("state",
            (XAttribute)self.name,
            new XAttribute("image", self.image),
            new XAttribute("gettable", self.gettable),
            new XElement("description", self.get),
            new XElement(self.conditionType + 's', self.conditions.OfTitle(self.conditionType))
        );
    }

    protected static T Parse<T>(XElement elt, string conditionType) where T: State, new() {
        return new T
        {
            name = NameSpec.Parse(elt),
            image = elt.GetFirst(X.Attr("image"), X.Elt("image")),
            description = elt.Elt("description"),
            get = elt.Elt("get"),
            gettable = int.Parse(elt.GetFirst(X.Attr("gettable"), X.Elt("gettable"))),
            conditionType = conditionType,
            conditions = elt.Element(conditionType).Elements().Select(ConditionSpec.Parse)
        };
    }
}

class Item
{
    public NameSpec name;
    public List<State> states;

    public static implicit operator XElement(Item self)
    {
        return new XElement("item", (XAttribute)self.name, new XElement("states", self.states.Cast<XElement>()));
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
            new XAttribute("image", self.image),
            new XAttribute("command", self.command),
            new XElement("response", self.response),
            new XElement("actions", self.actions.OfTitle("action"))
        );
    }
}

public class Program
{
    public static void Main(string[] args)
    {
        XElement house = XElement.Load("house.xml");
        Console.WriteLine(house);
    }
}
