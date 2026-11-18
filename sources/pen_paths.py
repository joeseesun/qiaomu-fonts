"""Read compact centerline drawings measured in x-height or cap-height units.

Each stroke consists of x,y,direction,pressure nodes separated by whitespace.
A slash separates strokes. A dash in place of a direction makes a straight
segment. Punchcutter varies the pen profile according to the family spec.
"""

from fontTools.agl import UV2AGL


def install(glyph, drawings):
    for character, drawing in drawings.items():
        codepoint = ord(character)
        name = UV2AGL.get(codepoint, f"uni{codepoint:04X}")
        if character in "0123456789":
            case = "fig"
        else:
            case = "lc" if character.islower() else "uc"
        glyph(name, codepoint, case)(make_drawer(drawing))


def make_drawer(drawing):
    strokes = []
    for line in drawing.split("/"):
        nodes = []
        for node in line.split():
            x, y, direction, pressure = node.split(",")
            nodes.append((float(x), float(y), direction, float(pressure)))
        strokes.append(nodes)

    def draw(context):
        height = context.cap if context.case in {"uc", "fig"} else context.xh
        for nodes in strokes:
            pen = context.P()
            for index, (x, y, direction, pressure) in enumerate(nodes):
                x, y = x * height, y * height
                if index == 0:
                    pen.m(x, y, direction, wm=pressure)
                elif direction == "-":
                    pen.l(x, y, wm=pressure)
                else:
                    pen.c(x, y, direction, wm=pressure)
            context.add(pen)

    return draw
