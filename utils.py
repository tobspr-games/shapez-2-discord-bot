import typing
from shapez2 import pygamePIL
import io

def pygameSurfToBytes(surf:pygamePIL.Surface) -> tuple[io.BytesIO,int]:
    with io.BytesIO() as buffer:
        pygamePIL.image_save(surf,buffer,"png")
        bufferValue = buffer.getvalue()
        bytesLen = len(bufferValue)
        finalBytes = io.BytesIO(bufferValue)
    return finalBytes, bytesLen

def decodeUnityFormat(text:str) -> list[dict[str,str|dict[str,bool|str]]]:
    tagNameToKey = {
        "b" : "bold",
        "color" : "color"
    }
    mode = "normal"
    curFormat = {
        "bold" : False,
        "color" : False
    }
    isClosingTag = False
    curText = ""
    decoded = []
    for char in text:
        closeTag = False
        if mode == "normal":
            if char == "<":
                mode = "tagName"
                decoded.append({
                    "format" : curFormat.copy(),
                    "text" : curText
                })
                curText = ""
                curTagName = ""
                curTagValue = ""
            else:
                curText += char
        elif mode == "tagName":
            if char == "/":
                isClosingTag = True
            elif char == ">":
                closeTag = True
            elif char == "=":
                mode = "tagValue"
            else:
                curTagName += char
        elif mode == "tagValue":
            if char == ">":
                closeTag = True
            else:
                curTagValue += char
        if closeTag:
            if isClosingTag:
                curFormat[tagNameToKey[curTagName]] = False
            else:
                if curTagValue == "":
                    curFormat[tagNameToKey[curTagName]] = True
                else:
                    curFormat[tagNameToKey[curTagName]] = curTagValue
            mode = "normal"
            isClosingTag = False
    decoded.append({
        "format" : curFormat.copy(),
        "text" : curText
    })
    return decoded

def decodedFormatToDiscordFormat(decoded:list[dict[str,str|dict[str,bool|str]]]) -> str:
    output = ""
    defaultFormat = {"bold":False,"color":False}
    previousFormat = defaultFormat
    for elem in [*decoded,{"format":defaultFormat,"text":""}]:
        curFormat = elem["format"]
        if curFormat["bold"] != previousFormat["bold"]:
            output += "**"
        elif curFormat["color"] != previousFormat["color"]:
            output += "__"
        output += elem["text"]
        previousFormat = curFormat
    return output

def decodeHexColor(hex:str) -> tuple[int,int,int]:
    return int(hex[:2],16), int(hex[2:4],16), int(hex[4:],16)

def decodedFormatToPygameSurf(decoded:list[dict[str,str|dict[str,bool|str]]],font:pygamePIL.font_Font,
    boldFont:pygamePIL.font_Font,antialias:bool|int,defaultColor:tuple[int,int,int]) -> pygamePIL.Surface:
    texts:list[pygamePIL.Surface] = []
    for elem in decoded:
        curFont = boldFont if elem["format"]["bold"] else font
        args = [elem["text"],antialias]
        if elem["format"]["color"] is False:
            args.append(defaultColor)
        else:
            args.append(decodeHexColor(elem["format"]["color"]))
        texts.append(curFont.render(*args))
    surf = pygamePIL.Surface((sum(t.get_width() for t in texts),max(t.get_height() for t in texts)),pygamePIL.SRCALPHA)
    curX = 0
    for text in texts:
        surf.blit(text,(curX,(surf.get_height()/2)-(text.get_height()/2)))
        curX += text.get_width()
    return surf

def sepInGroupsNumber(num:int|float) -> str:
    return f"{num:,}"



class OutputString:

    class Number:
        def __init__(self,num:int|float,isIndex:bool=False) -> None:
            self.num = num
            self.isIndex = isIndex

    class UnsafeString:
        def __init__(self,string:str) -> None:
            self.string = string

    class UnsafeNumber:
        def __init__(self,num:int|float,isIndex:bool=False) -> None:
            self.num = num
            self.isIndex = isIndex

    def __init__(self,*elems:str|Number|UnsafeString|UnsafeNumber|typing.Self) -> None:
        self.elems = list(elems)

    def render(self,isShownPublicly:bool) -> str:

        output = ""
        for elem in self.elems:
            elemType = type(elem)

            if elemType == str:
                output += elem

            elif elemType == OutputString.UnsafeString:
                if isShownPublicly:
                    output += f"<{len(elem.string)} character(s) long string not shown because public>"
                else:
                    output += elem.string

            elif elemType == OutputString.Number:
                output += str(elem.num + (1 if elem.isIndex else 0))

            elif elemType == OutputString.UnsafeNumber:
                output += str(elem.num + (1 if elem.isIndex else 0))

            elif elemType == OutputString:
                output += elem.render(isShownPublicly)

            else:
                raise TypeError(f"Unknown elem type in OutputString.elems while executing 'render' function : {elemType.__name__}")

        return output