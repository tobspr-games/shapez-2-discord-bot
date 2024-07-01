import globalInfos
import discord
import pygamePIL
import io

async def _debugMenuCheck(message:discord.Message) -> str|None:

    PATTERN_COLOR = (64,166,204,255)
    PATTERN_WIDTH = 9
    PATTERN_HEIGHT = 14
    PATTERN_MAX_X = 15
    PATTERN_MAX_Y = 22
    PATTERN = [
        (6,  0), (7,  0), (8,  0),
        (6,  1), (7,  1), (8,  1),
        (4,  2), (5,  2), (6,  2),
        (3,  3), (4,  3), (5,  3),
        (3,  4), (4,  4), (5,  4),
        (1,  5), (2,  5), (3,  5),
        (0,  6), (1,  6), (2,  6),
        (0,  7), (1,  7), (2,  7),
        (1,  8), (2,  8), (3,  8),
        (3,  9), (4,  9), (5,  9),
        (3, 10), (4, 10), (5, 10),
        (4, 11), (5, 11), (6, 11),
        (6, 12), (7, 12), (8, 12),
        (6, 13), (7, 13), (8, 13)
    ]

    if len(message.attachments) != 1:
        return None

    attachement = message.attachments[0]

    if attachement.size > globalInfos.MAX_DOWNLOAD_IMAGE_FILE_SIZE:
        return None

    try:
        imageBytes = await attachement.read()
    except (discord.HTTPException,discord.NotFound):
        return None

    with io.BytesIO(imageBytes) as buffer:
        try:
            image = pygamePIL.image_load(buffer)
        except pygamePIL.error:
            return None

    imageWidth, imageHeight = image.get_size()

    for xOffset in range(PATTERN_MAX_X+1):
        for yOffset in range(PATTERN_MAX_Y+1):

            if ((imageWidth-xOffset) < PATTERN_WIDTH) or ((imageHeight-yOffset) < PATTERN_HEIGHT):
                continue

            hasPattern = True
            for x,y in PATTERN:
                if image.get_at((x+xOffset,y+yOffset)) != PATTERN_COLOR:
                    hasPattern = False
                    break

            if hasPattern:
                return "The image in your message might contain a menu that can be closed by pressing ctrl+backspace."

    return None

async def checkMessage(message:discord.Message) -> list[str]:

    messages = []

    debugMenuCheckResult = await _debugMenuCheck(message)
    if debugMenuCheckResult is not None:
        messages.append(debugMenuCheckResult)

    return messages