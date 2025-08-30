import shapeViewerWrapper
import globalInfos
import operationGraph
import utils
# import researchViewer
import guildSettings
import shapeCodeGenerator
import autoMessages

import shapez2 as spz2
import discord
import json
import sys
import traceback
import io
import typing
import datetime
import os



#region utility functions

async def globalLogMessage(message:str,sendInCodeBlock:bool=False) -> None:
    if globalInfos.GLOBAL_LOG_CHANNEL is None:
        print(message)
    else:
        logChannel = client.get_channel(globalInfos.GLOBAL_LOG_CHANNEL)
        assert isinstance(logChannel,discord.TextChannel)
        await logChannel.send(**getCommandResponse(
            message,None,logChannel.guild,True,
            ("```","```") if sendInCodeBlock else ("","")
        ))

async def globalLogError() -> None:
    await globalLogMessage(("".join(traceback.format_exception(*sys.exc_info())))[:-1],True)

async def useShapeViewer(userMessage:str,sendErrors:bool,userId:int) -> tuple[bool,str,tuple[discord.File,int]|None]:

    msgParts = []
    hasErrors = False
    file = None
    imageSize = None

    def inner() -> None:
        nonlocal hasErrors, file, imageSize

        renderResult = shapeViewerWrapper.renderShapes(userMessage)

        if not renderResult["hasPotentialShapeCodes"]:
            if sendErrors:
                msgParts.append(renderResult["errorMsgs"][0])
            return

        if len(renderResult["errorMsgs"]) > 0:
            hasErrors = True
            if sendErrors:
                msgParts.append("**Error messages :**\n"+"\n".join(f"- {msg}" for msg in renderResult["errorMsgs"]))

        if renderResult["finalImage"] is None:
            return

        file = discord.File(renderResult["finalImage"][0],"shapes.png",spoiler=renderResult["spoiler"])
        imageSize = renderResult["finalImage"][1]

        if renderResult["shapeCodes"] is not None:
            msgParts.append(
                "**Resulting shape codes :**\n"+
                "\n".join(
                    " ".join(f"{{{code}}}" for code in codeGroup)
                    for codeGroup in discord.utils.as_chunks(renderResult["shapeCodes"],globalInfos.SHAPES_PER_ROW)
                )
            )

        if renderResult["viewer3dLinks"] is not None:
            msgParts.append(
                "**3D viewer links :**\n"+
                "\n".join(
                    " ".join(f"{{{link}}}" for link in linkGroup)
                    for linkGroup in discord.utils.as_chunks(renderResult["viewer3dLinks"],globalInfos.SHAPES_PER_ROW)
                )
            )

    try:

        inner()

        curTime = getCurrentTime()
        for user in list(shapeViewerLastErrors.keys()):
            if (curTime-shapeViewerLastErrors[user]["timestamp"]) > datetime.timedelta(seconds=globalInfos.SHAPE_VIEWER_SLASH_CMD_TIP_TIME_INTERVAL_SECONDS):
                shapeViewerLastErrors.pop(user)
        if hasErrors and (not sendErrors):
            curInfo = shapeViewerLastErrors.get(userId)
            if curInfo is None:
                shapeViewerLastErrors[userId] = {"count":1,"timestamp":curTime}
            else:
                curInfo["count"] += 1
                curInfo["timestamp"] = curTime
                if curInfo["count"] >= globalInfos.SHAPE_VIEWER_SLASH_CMD_TIP_NUM_ERRORS:
                    msgParts.append("Tip : Use the </view-shapes:1132698874839044166> command to view error messages")
                    shapeViewerLastErrors.pop(userId)
        else:
            shapeViewerLastErrors.pop(userId,None)

        responseMsg = "\n\n".join(msgParts)

        return hasErrors, responseMsg, (None if file is None else (file, imageSize))
    except Exception as e:
        await globalLogError()
        return True, f"{globalInfos.UNKNOWN_ERROR_TEXT} ({e.__class__.__name__})" if sendErrors else "", None

def getCurrentTime() -> datetime.datetime:
    return discord.utils.utcnow()

def isDisabledInGuild(guildId:int|None) -> bool:

    if globalInfos.RESTRICT_TO_GUILDS is None:
        return False

    if guildId in globalInfos.RESTRICT_TO_GUILDS:
        return False

    return True

def exitCommandWithoutResponse(interaction:discord.Interaction) -> bool:

    if globalPaused:
        return True

    if isDisabledInGuild(interaction.guild_id):
        return True

    return False

async def isInCooldown(userId:int,guildId:int|None) -> bool:

    lastTriggered = usageCooldownLastTriggered.get((userId,guildId))

    if lastTriggered is None:
        return False

    if guildId is None:
        cooldown = globalInfos.NO_GUILD_USAGE_COOLDOWN_SECONDS
    else:
        cooldown = (await guildSettings.getGuildSettings(guildId))["usageCooldown"]

    delta = getCurrentTime() - lastTriggered

    if delta < datetime.timedelta(seconds=cooldown):
        return True

    return False

def setUserCooldown(userId:int,guildId:int|None) -> None:
    usageCooldownLastTriggered[(userId,guildId)] = getCurrentTime()

class PermissionLvls:

    PUBLIC_FEATURE = 0
    REACTION = 1
    PRIVATE_FEATURE = 2
    ADMIN = 3
    OWNER = 4

async def hasPermission(requestedLvl:int,*,message:discord.Message|None=None,interaction:discord.Interaction|None=None) -> bool:

    if message is not None:

        userId = message.author.id
        channelId = message.channel.id
        if message.guild is None:
            guildId = None
        else:
            guildId = message.guild.id
            if isinstance(message.author,discord.User):
                userRoles = []
                adminPerm = False
            else:
                userRoles = message.author.roles[1:]
                adminPerm = message.author.guild_permissions.administrator

    elif interaction is not None:

        userId = interaction.user.id
        channelId = interaction.channel_id
        guildId = interaction.guild_id
        if interaction.guild is not None:
            if isinstance(interaction.user,discord.User):
                userRoles = []
                adminPerm = False
            else:
                userRoles = interaction.user.roles[1:]
                adminPerm = interaction.user.guild_permissions.administrator

    else:
        raise ValueError("No message or interaction in 'hasPermission' function")

    async def inner() -> bool:

        if (guildId is None) and (requestedLvl == PermissionLvls.ADMIN):
            return False

        if userId in globalInfos.OWNER_USERS:
            return True
        else:
            if requestedLvl == PermissionLvls.OWNER:
                return False

        if globalPaused:
            return False

        if isDisabledInGuild(guildId):
            return False

        if guildId is None:
            if await isInCooldown(userId,guildId):
                return False
            return requestedLvl < PermissionLvls.ADMIN

        curGuildSettings = await guildSettings.getGuildSettings(guildId)

        if adminPerm:
            isAdmin = True
        else:
            isAdmin = False
            adminRoles = curGuildSettings["adminRoles"]
            for role in userRoles:
                if role.id in adminRoles:
                    isAdmin = True
                    break
        if isAdmin:
            if requestedLvl <= PermissionLvls.ADMIN:
                return True
        else:
            if requestedLvl == PermissionLvls.ADMIN:
                return False

        if await isInCooldown(userId,guildId):
            return False

        if requestedLvl == PermissionLvls.PRIVATE_FEATURE:
            return True

        if curGuildSettings["paused"]:
            return False

        if requestedLvl == PermissionLvls.REACTION:
            return True

        # requestedLvl = public feature

        if curGuildSettings["restrictToChannel"] not in (None,channelId):
            return False

        restrictToRoles = curGuildSettings["restrictToRoles"]
        if restrictToRoles == []:
            return True

        restrictToRolesInverted = curGuildSettings["restrictToRolesInverted"]
        for role in userRoles:
            roleInRestrictToRoles = role.id in restrictToRoles
            if restrictToRolesInverted and (not roleInRestrictToRoles):
                return True
            if (not restrictToRolesInverted) and roleInRestrictToRoles:
                return True

        return False

    toReturn = await inner()
    if toReturn:
        setUserCooldown(userId,guildId)
    return toReturn

def msgToFile(msg:str,filename:str,guild:discord.Guild|None) -> discord.File|None:
    msgBytes = msg.encode()
    if isFileTooBig(len(msgBytes),guild):
        return None
    return discord.File(io.BytesIO(msgBytes),filename)

async def decodeAttachment(file:discord.Attachment) -> str|None:
    if file.size > globalInfos.MAX_DOWNLOAD_TEXT_FILE_SIZE:
        return None
    try:
        fileBytes = await file.read()
    except (discord.HTTPException,discord.NotFound):
        return None
    try:
        fileStr = fileBytes.decode()
    except UnicodeDecodeError:
        return None
    return fileStr

def isFileTooBig(fileSize:int,guild:discord.Guild|None) -> bool:
    if guild is None:
        return fileSize > discord.utils.DEFAULT_FILE_SIZE_LIMIT_BYTES
    return fileSize > guild.filesize_limit

BP_VERSION_REACTION_A = "\U0001f1e6"
BP_VERSION_REACTION_C = "\U0001f1e8"
BP_VERSION_REACTION_D = "\U0001f1e9"
BP_VERSION_REACTION_P = "\U0001f1f5"
BP_VERSION_REACTION_R = "\U0001f1f7"
BP_VERSION_REACTION_DOT_1 = "\u23fa"
BP_VERSION_REACTION_DOT_2 = 1261037521496965202
BP_VERSION_REACTION_DOT_3 = 1333165681281339503
BP_VERSION_REACTION_DIGITS:list[dict[str,str|int]] = [
    {str(i) : f"{i}\ufe0f\u20e3" for i in range(10)},
    {str(i) : v for i,v in enumerate([
        1159909769876877352,1159909772133400707,1159909773643358228,
        1159909775526592512,1159909784305283133,1159909786956087326,
        1159909788130476124,1159909789741105282,1159909792106676405,
        1159909793578877028
    ])},
    {str(i) : v for i,v in enumerate([
        1159909533074866286,1159909535872471162,1159909537944457226,
        1159909542193270824,1159909546735702108,1159909549323587757,
        1159909551697576056,1159909554532913203,1159909556336468008,
        1159909559066964110
    ])},
    {str(i) : v for i,v in enumerate([
        1333173576563687516,1333173578148876319,1333173580166463569,
        1333173581474959372,1333173589674954832,1333173591365255329,
        1333173593269469244,1333173594930413579,1333173596901867530,
        1333173598407626752
    ])},
    {str(i) : v for i,v in enumerate([
        1333173698345177138,1333173700429746297,1333173701830643847,
        1333173704078921842,1333173705756512297,1333173708008849540,
        1333173709531250708,1333173712148627516,1333173713822286006,
        1333173715554275430
    ])},
    {str(i) : v for i,v in enumerate([
        1333173795329933424,1333173796936482897,1333173798458888262,
        1333173800145129523,1333173801659400326,1333173803358093393,
        1333173805409107968,1333173807095218248,1333173808609361940,
        1333173811171954800
    ])}
]

def versionNumToReactions(version:int) -> None|list[str|int]:

    versionIds = spz2.versions.GAME_VERSIONS.get(version)

    if versionIds is None:
        return None

    decomposed = spz2.versions.getVersionNameFromId(versionIds[-1])

    output:list[str|int] = [
        BP_VERSION_REACTION_DIGITS[0][decomposed.major],
        BP_VERSION_REACTION_DOT_1,
        BP_VERSION_REACTION_DIGITS[1][decomposed.minor],
        BP_VERSION_REACTION_DOT_2,
        BP_VERSION_REACTION_DIGITS[2][decomposed.patch]
    ]

    digitsIndex = 3

    for suffix in decomposed.suffixes:

        if isinstance(suffix,spz2.versions.AlphaSuffix):
            output.append(BP_VERSION_REACTION_A)
            for num in suffix.version:
                output.append(BP_VERSION_REACTION_DIGITS[digitsIndex][num])
                digitsIndex += 1
            if suffix.subVersion is not None:
                output.append(BP_VERSION_REACTION_DOT_3)
                output.append(BP_VERSION_REACTION_DIGITS[digitsIndex][suffix.subVersion])
                digitsIndex += 1

        elif isinstance(suffix,spz2.versions.ReleaseCandidateSuffix):
            output.extend([BP_VERSION_REACTION_R,BP_VERSION_REACTION_C])
            output.append(BP_VERSION_REACTION_DIGITS[digitsIndex][suffix.number])
            digitsIndex += 1

        elif isinstance(suffix,spz2.versions.PreviewSuffix):
            output.append(BP_VERSION_REACTION_P)
            output.append(BP_VERSION_REACTION_DIGITS[digitsIndex][suffix.number])
            digitsIndex += 1

        elif isinstance(suffix,spz2.versions.DemoSuffix):
            output.append(BP_VERSION_REACTION_D)

    return output

def detectBPVersion(potentialBPCodes:list[str]) -> list[str|int]|None:

    versions = []

    for bp in potentialBPCodes:

        try:
            version = spz2.blueprints.getBlueprintVersion(bp)
        except spz2.blueprints.BlueprintError:
            continue

        versionReaction = versionNumToReactions(version)

        if versionReaction is None:
            continue

        versions.append(versionReaction)

    if len(versions) != 1:
        return None

    return versions[0]

def safenString(string:str) -> str:
    return discord.utils.escape_mentions(string)

async def getBPFromStringOrFile(string:str|None,file:discord.Attachment|None) -> tuple[bool,str]:
    if file is None:
        if string is None:
            return False, "Either a blueprint code or a blueprint file must be provided"
        toReturn = string
    else:
        if string is not None:
            return False, "A blueprint code and a blueprint file can't be both provided at the same time"
        toReturn = await decodeAttachment(file)
        if toReturn is None:
            return False, "Error while processing blueprint file"
    return True, toReturn.strip()

class getCommandResponseReturn(typing.TypedDict):
    content:typing.NotRequired[str]
    file:typing.NotRequired[discord.File]

def getCommandResponse(
    text:str,
    file:tuple[discord.File,int]|None,
    guild:discord.Guild|None,
    public:bool,
    notInFileFormat:tuple[str,str]=("","")
) -> getCommandResponseReturn:
    kwargs:getCommandResponseReturn = {}

    if len(notInFileFormat[0])+len(text)+len(notInFileFormat[1]) > globalInfos.MESSAGE_MAX_LENGTH:
        if file is None:
            textFile = msgToFile(text,"response.txt",guild)
            if textFile is None:
                kwargs["content"] = globalInfos.MESSAGE_TOO_LONG_TEXT
            else:
                kwargs["file"] = textFile
        else:
            kwargs["content"] = globalInfos.MESSAGE_TOO_LONG_TEXT
    else:
        text = notInFileFormat[0] + text + notInFileFormat[1]
        if public:
            text = safenString(text)
        kwargs["content"] = text

    if file is not None:
        if isFileTooBig(file[1],guild):
            kwargs["file"] = discord.File(globalInfos.FILE_TOO_BIG_PATH)
        else:
            kwargs["file"] = file[0]

    return kwargs

async def interactionErrorHandler(interaction:discord.Interaction,error:BaseException) -> None:
    await globalLogError()
    responseMsg = f"{globalInfos.UNKNOWN_ERROR_TEXT} ({error.__class__.__name__})"
    if interaction.response.is_done():
        await interaction.followup.send(responseMsg)
    else:
        await interaction.response.send_message(responseMsg,ephemeral=True)

class AntispamAlertButtons(discord.ui.View):

    REASON_MSG = "Request by moderator from antispam alert"

    def __init__(self,userId:int,buttonStates:str="1111"):
        super().__init__()
        self.add_item(discord.ui.Button(
            label = "Send info DM",
            style = discord.ButtonStyle.blurple,
            custom_id = f"antispam-sendDM-{userId}-{buttonStates}",
            disabled = buttonStates[0] == "0"
        ))
        self.add_item(discord.ui.Button(
            label = "Un-timeout",
            style = discord.ButtonStyle.green,
            custom_id = f"antispam-untimeout-{userId}-{buttonStates}",
            disabled = buttonStates[1] == "0"
        ))
        self.add_item(discord.ui.Button(
            label = "Kick",
            style = discord.ButtonStyle.red,
            custom_id = f"antispam-kick-{userId}-{buttonStates}",
            disabled = buttonStates[2] == "0"
        ))
        self.add_item(discord.ui.Button(
            label = "Ban",
            style = discord.ButtonStyle.red,
            custom_id = f"antispam-ban-{userId}-{buttonStates}",
            disabled = buttonStates[3] == "0"
        ))

async def antispamAlertButtonInteraction(interaction:discord.Interaction,rawAction:str) -> None:

    action, userId, buttonStates = rawAction.split("-")
    assert interaction.guild is not None
    assert interaction.message is not None
    userIdInt = int(userId)

    try:
        user = await interaction.guild.fetch_member(userIdInt)
    except (discord.Forbidden,discord.NotFound):
        user = None

    if user is None:
        responseMsg = "Couldn't find user"
        disableIndexes = []

    elif action == "sendDM":
        try:
            await user.send(globalInfos.ANTISPAM_DM_MSG)
            responseMsg = "Succesfully sent DM"
        except discord.Forbidden:
            responseMsg = "Failed to send DM"
        disableIndexes = [0]

    elif action == "untimeout":
        try:
            await user.timeout(None,reason=AntispamAlertButtons.REASON_MSG)
            responseMsg = "Succesfully un-timed out user"
        except (discord.Forbidden,discord.NotFound):
            responseMsg = "Failed to un-timeout user"
        disableIndexes = [1]

    elif action == "kick":
        try:
            await user.kick(reason=AntispamAlertButtons.REASON_MSG)
            responseMsg = "Succesfully kicked user"
        except (discord.Forbidden,discord.NotFound):
            responseMsg = "Failed to kick user"
        disableIndexes = list(range(4))

    elif action == "ban":
        try:
            await user.ban(delete_message_days=0,reason=AntispamAlertButtons.REASON_MSG)
            responseMsg = "Succesfully banned user"
        except (discord.Forbidden,discord.NotFound):
            responseMsg = "Failed to ban user"
        disableIndexes = list(range(4))

    else:
        raise ValueError(f"Unknown antispam action : {action}")

    await interaction.response.send_message(responseMsg,ephemeral=True)
    buttonStates = "".join("0" if i in disableIndexes else state for i,state in enumerate(buttonStates))
    await interaction.message.edit(view=AntispamAlertButtons(userIdInt,buttonStates))

# port of sbe's antispam feature with difference of being separated per server and possiblity of sending an alert when triggered
async def antiSpam(message:discord.Message) -> typing.Literal[True]|None:

    async def sendAlert() -> None:

        curAlertChannel = curGuildSettings["antispamAlertChannel"]
        if curAlertChannel is None:
            return

        curAlertChannel = client.get_channel(curAlertChannel)
        if not isinstance(curAlertChannel,(discord.TextChannel,discord.Thread)):
            return

        alertMsg = f"{message.author.mention} triggered the antispam :"
        msgContentFile = msgToFile(msgContent,"messageContent.txt",curAlertChannel.guild)
        kwargs = {}
        if msgContentFile is None:
            alertMsg += " <couldn't put message content in a file>"
        else:
            kwargs["file"] = msgContentFile

        await curAlertChannel.send(alertMsg,view=AntispamAlertButtons(message.author.id),**kwargs)

    if globalPaused:
        return

    if message.author.bot:
        return

    if message.guild is None:
        return

    if isDisabledInGuild(message.guild.id):
        return

    curGuildSettings = await guildSettings.getGuildSettings(message.guild.id)

    if not curGuildSettings["antispamEnabled"]:
        return

    if message.content == "": # message consists of only attachments
        return

    userId = message.author.id
    guildId = message.guild.id
    curGuildMember = (userId,guildId)
    msgContent = message.content
    curTime = getCurrentTime()

    for guildMember in list(antiSpamLastMessages.keys()):
        if (
            (curTime - antiSpamLastMessages[guildMember]["timestamp"])
            > datetime.timedelta(seconds=globalInfos.ANTISPAM_TIME_INTERVAL_SECONDS)
        ):
            antiSpamLastMessages.pop(guildMember)

    curInfo = antiSpamLastMessages.get(curGuildMember)

    if (curInfo is None) or (curInfo["content"] != msgContent):
        newInfo:antiSpamLastMessagesType = {
            "content" : msgContent,
            "messages" : [message],
            "count" : 1,
            "timestamp" : curTime
        }
        antiSpamLastMessages[curGuildMember] = newInfo
        return

    curInfo["messages"].append(message)
    curInfo["count"] += 1
    curInfo["timestamp"] = curTime

    if (
        isinstance(message.author,discord.Member)
        and (message.author.joined_at is not None)
        and (
            (curTime-message.author.joined_at)
            < datetime.timedelta(hours=globalInfos.ANTISPAM_NEW_MEMBER_PERIOD_HOURS)
        )
    ):
        curThreshold = globalInfos.ANTISPAM_MSG_COUNT_NEW_MEMBER_THRESHOLD
    else:
        curThreshold = globalInfos.ANTISPAM_MSG_COUNT_THRESHOLD

    if curInfo["count"] < curThreshold:
        return

    if (isinstance(message.author,discord.User)) or (message.author.is_timed_out()):
        return

    try:
        await message.author.timeout(
            datetime.timedelta(seconds=globalInfos.ANTISPAM_TIMEOUT_SECONDS),
            reason=f"antispam: {msgContent}"
        )
    except discord.Forbidden:
        await globalLogMessage(f"Failed to timeout {message.author.id} for antispam")
        return

    # port difference : only delete if permission to timeout
    for msg in curInfo["messages"]:
        try:
            await msg.delete()
        except (discord.Forbidden,discord.NotFound) as e:
            await globalLogMessage(f"Failed to delete {msg.jump_url} for antispam ({e.__class__.__name__})")

    await sendAlert()
    return True

async def concatMsgContentAndAttachments(content:str,attachments:list[discord.Attachment]) -> str:
    for file in attachments:
        fileContent = await decodeAttachment(file)
        if fileContent is None:
            continue
        content += fileContent
    return content

def getBPInfoText(blueprint:spz2.blueprints.Blueprint,advanced:bool) -> str:

    def formatCounts(bp:spz2.blueprints.BuildingBlueprint|spz2.blueprints.IslandBlueprint|None,name:str) -> str:
        output = f"\n**{name} counts :**\n"
        if bp is None:
            output += "None"
        else:
            if isinstance(bp,spz2.blueprints.BuildingBlueprint):
                counts = bp.getBuildingCounts()
                lines = []
                for bv,bc in spz2.buildings.getCategorizedBuildingCounts(counts).items():
                    lines.append(f"- `{bv.title.translate().renderToStringNoFeatures()}` : `{utils.sepInGroupsNumber(sum(bc.values()))}`")
                    for biv,c in bc.items():
                        lines.append(f"  - `{biv.id}` : `{utils.sepInGroupsNumber(c)}`")
                output += "\n".join(lines)
            else:
                counts = bp.getIslandCounts()
                lines = []
                for ig,ic in spz2.islands.getCategorizedIslandCounts(counts).items():
                    lines.append(f"- `{ig.title.translate().renderToStringNoFeatures()}` : `{utils.sepInGroupsNumber(sum(ic.values()))}`")
                    for i,c in ic.items():
                        lines.append(f"  - `{i.title.translate().renderToStringNoFeatures()}` : `{utils.sepInGroupsNumber(c)}`")
                output += "\n".join(lines)
        return output

    versionIds = spz2.versions.GAME_VERSIONS.get(blueprint.version)
    if versionIds is None:
        versionTxt = "Unknown"
    else:
        if not advanced:
            versionIds = versionIds[-1:]
        versionNames = [spz2.versions.getVersionNameFromId(v) for v in versionIds]
        versionStrings = [spz2.versions.versionNameToString(v) for v in versionNames]
        if advanced:
            versionTxt = f"[{', '.join(f"`{v}`" for v in versionStrings)}]"
        else:
            versionTxt = f"`{versionStrings[0]}`"
    bpTypeTxt = "Platform" if blueprint.type == spz2.blueprints.BlueprintType.island else "Building"
    try:
        bpCost = f"`{utils.sepInGroupsNumber(blueprint.getCost())}`"
    except spz2.blueprints.BlueprintError:
        bpCost = f"<Failed to compute>"

    responseParts = [[
        f"Version : `{blueprint.version}` / {versionTxt}",
        f"Blueprint type : `{bpTypeTxt}`",
        f"Blueprint cost : {bpCost}",
        f"Platform unit cost : `{utils.sepInGroupsNumber(blueprint.getIslandUnitCost())}`"
    ]]

    if blueprint.buildingBP is not None:
        buildingSize = blueprint.buildingBP.getSize()
        responseParts.append([
            f"Building count : `{utils.sepInGroupsNumber(blueprint.buildingBP.getBuildingCount())}`",
            f"Building size : `{buildingSize.width}`x`{buildingSize.height}`x`{buildingSize.depth}`",
            f"Building tiles : `{utils.sepInGroupsNumber(blueprint.buildingBP.getTileCount())}`"
        ])

    if blueprint.islandBP is not None:
        islandSize = blueprint.islandBP.getSize()
        responseParts.append([
            f"Platform count : `{utils.sepInGroupsNumber(blueprint.islandBP.getIslandCount())}`",
            f"Platform size : `{islandSize.width}`x`{islandSize.height}`x`{islandSize.depth}`",
            f"Platform tiles : `{utils.sepInGroupsNumber(blueprint.islandBP.getTileCount())}`"
        ])

    blueprintIconsStr = []
    for icon in blueprint.innerBlueprint.getValidIcons():
        if icon.type == spz2.blueprints.BlueprintIconType.empty:
            blueprintIconsStr.append("<empty>")
        elif icon.type == spz2.blueprints.BlueprintIconType.icon:
            blueprintIconsStr.append(f"`{icon.icon}`")
        else:
            blueprintIconsStr.append(f"{{{icon.shape.toShapeCode()}}}")

    responseParts.append([
        f"Icons : {', '.join(blueprintIconsStr)}"
    ])

    finalOutput = "\n".join(", ".join(part) for part in responseParts)

    if advanced:
        finalOutput += formatCounts(blueprint.buildingBP,"Building")
        finalOutput += formatCounts(blueprint.islandBP,"Platform")

    return finalOutput

def getAccessBPTextAndFiles(
    blueprint:spz2.blueprints.Blueprint,
    blueprintCode:str,
    guild:discord.Guild|None,
    includeBigFiles:bool
) -> tuple[str,list[discord.File]]:

    infoText = getBPInfoText(blueprint,False)
    infoTextFormatted = "**Blueprint Infos :**\n" + "\n".join(f"> {l}" for l in infoText.split("\n"))

    bpCodeLinkSafe = blueprintCode
    for old,new in globalInfos.LINK_CHAR_REPLACEMENT.items():
        bpCodeLinkSafe = bpCodeLinkSafe.replace(old,new)
    bpCode3dViewLink = f"{globalInfos.BLUEPRINT_3D_VIEWER_LINK_START}{bpCodeLinkSafe}"
    bpCode3dViewLinkFormatted = f"**Actions :**\n> [[View in 3D]](<{bpCode3dViewLink}>)"

    responseMsg = infoTextFormatted + "\n" + bpCode3dViewLinkFormatted

    toCreateFiles:list[tuple[str,str]] = []

    if len(responseMsg) > globalInfos.MESSAGE_MAX_LENGTH:
        if len(infoTextFormatted) <= globalInfos.MESSAGE_MAX_LENGTH:
            responseMsg = infoTextFormatted
            if includeBigFiles:
                toCreateFiles.append((bpCode3dViewLink,"3D viewer link.txt"))
        elif len(bpCode3dViewLinkFormatted) <= globalInfos.MESSAGE_MAX_LENGTH:
            responseMsg = bpCode3dViewLinkFormatted
            toCreateFiles.append((infoText,"blueprint infos.txt"))
        else:
            responseMsg = ""
            toCreateFiles.append(("\n".join([
                "Blueprint Infos :",
                infoText,
                "3D Viewer Link :",
                bpCode3dViewLink
            ]),"blueprint infos.txt"))

    if includeBigFiles:
        toCreateFiles.append((blueprintCode,"blueprint.txt"))
        toCreateFiles.append((blueprintCode,"blueprint.spz2bp"))

    files = []
    fileTooBig = False

    for fileContent,fileName in toCreateFiles:
        file = msgToFile(fileContent,fileName,guild)
        if file is None:
            fileTooBig = True
        else:
            files.append(file)

    if fileTooBig:
        files.append(discord.File(globalInfos.FILE_TOO_BIG_PATH))

    return responseMsg, files

async def accessBlueprintCommandInnerPart(
    interaction:discord.Interaction,
    getBPCode:typing.Coroutine[typing.Any,typing.Any,tuple[bool,str]]
) -> None:
    if exitCommandWithoutResponse(interaction):
        return

    async def inner() -> None:
        nonlocal responseMsg, files
        files = []

        await interaction.response.defer(ephemeral=True)

        if not await hasPermission(PermissionLvls.PRIVATE_FEATURE,interaction=interaction):
            responseMsg = globalInfos.NO_PERMISSION_TEXT
            return

        valid, errorOrBP = await getBPCode
        if not valid:
            responseMsg = errorOrBP
            return

        try:
            decodedBP = spz2.blueprints.decodeBlueprint(errorOrBP)
        except spz2.blueprints.BlueprintError as e:
            responseMsg = f"Error while decoding blueprint : {e}"
            return

        responseMsg, files = getAccessBPTextAndFiles(decodedBP,errorOrBP,interaction.guild,True)

    responseMsg = ""
    files = []
    await inner()
    await interaction.followup.send(responseMsg,files=files,ephemeral=True) # ephemeral required for button interactions

async def getSinglePotentialBPCodeInMessage(message:discord.Message) -> str|None:
    potentialBPCodes = spz2.blueprints.getPotentialBPCodesInString(
        await concatMsgContentAndAttachments(message.content,message.attachments)
    )
    if len(potentialBPCodes) != 1:
        return None
    return potentialBPCodes[0]

async def accessBlueprintCommandFromMessage(interaction:discord.Interaction,message:discord.Message) -> None:

    async def getBPCode() -> tuple[bool,str]:
        potentialBPCode = await getSinglePotentialBPCodeInMessage(message)
        if potentialBPCode is None:
            return False, "Message doesn't contain exactly one blueprint code"
        return True, potentialBPCode

    await accessBlueprintCommandInnerPart(interaction,getBPCode())

class BPInfoMessageButtons(discord.ui.View):
    def __init__(self):
        super().__init__()
        self.add_item(discord.ui.Button(
            label = "View in 3D / Convert file format",
            style = discord.ButtonStyle.grey,
            custom_id = "accessBP"
        ))

async def bpInfoMessageButtonInteraction(interaction:discord.Interaction) -> None:

    assert interaction.message is not None
    assert interaction.message.type == discord.MessageType.reply
    assert isinstance(interaction.channel,discord.abc.Messageable)

    msgRef = interaction.message.reference
    assert msgRef is not None
    assert msgRef.message_id is not None

    async def notFound() -> None:
        await interaction.response.send_message("Can't access original message",ephemeral=True)

    if isinstance(msgRef.resolved,discord.DeletedReferencedMessage):
        await notFound()
        return

    if msgRef.resolved is None:
        try:
            message = await interaction.channel.fetch_message(msgRef.message_id)
        except discord.NotFound:
            await notFound()
            return
    else:
        message = msgRef.resolved

    await accessBlueprintCommandFromMessage(interaction,message)

#endregion



#region events

def runDiscordBot() -> None:

    global client, msgCommandMessages

    intents = discord.Intents.all()
    intents.presences = False
    client = discord.Client(intents=intents,activity=discord.Game("shapez 2"))
    tree = discord.app_commands.CommandTree(client)

    with open(globalInfos.MSG_COMMAND_MESSAGES_PATH,encoding="utf-8") as f:
        msgCommandMessages = json.load(f)

    @client.event
    async def on_ready() -> None:
        global executedOnReady
        if not executedOnReady:
            await tree.sync()
            print(f"{client.user} is now running")
            executedOnReady = True

    @client.event
    async def on_error(event:str,*args,**kwargs) -> None:
        await globalLogError()
        if event == "on_interaction":
            curExc = sys.exception()
            assert curExc is not None
            await interactionErrorHandler(args[0],curExc)

    @client.event
    async def on_message(message:discord.Message) -> None:

        if message.author == client.user:
            return

        if (await antiSpam(message)) is True:
            return

        reactedToBPCodeInMsg = False

        publicPerm = await hasPermission(PermissionLvls.PUBLIC_FEATURE,message=message)
        if publicPerm:

            # shape viewer
            hasErrors, responseMsg, file = await useShapeViewer(message.content,False,message.author.id)
            if hasErrors:
                await message.add_reaction(globalInfos.INVALID_SHAPE_CODE_REACTION)
            if (responseMsg != "") or (file is not None):
                await message.channel.send(**getCommandResponse(responseMsg,file,message.guild,True))

            # automatic messages
            autoMsgResult = await autoMessages.checkMessage(message)
            if autoMsgResult != []:
                responseMsg = "\n".join(autoMsgResult)
                try:
                    await message.reply(**getCommandResponse(responseMsg,None,message.guild,True),mention_author=False)
                except discord.HTTPException: # error raised when og message was deleted
                    pass

            # bp info message
            async def bpInfoMessageLogic() -> None:
                nonlocal reactedToBPCodeInMsg
                if message.guild is None:
                    return
                curBlueprintsChannels = (await guildSettings.getGuildSettings(message.guild.id))["blueprintsChannels"]
                if type(message.channel) == discord.Thread:
                    if message.channel.parent_id not in curBlueprintsChannels:
                        return
                else:
                    if message.channel.id not in curBlueprintsChannels:
                        return
                potentialBP = await getSinglePotentialBPCodeInMessage(message)
                if potentialBP is None:
                    return
                try:
                    decodedBP = spz2.blueprints.decodeBlueprint(potentialBP)
                except spz2.blueprints.BlueprintError:
                    return
                responseMsg, files = getAccessBPTextAndFiles(decodedBP,potentialBP,message.guild,False)
                try:
                    await message.reply(
                        safenString(responseMsg),
                        files=files,
                        mention_author=False,
                        view=BPInfoMessageButtons()
                    )
                except discord.HTTPException:
                    return
                reactedToBPCodeInMsg = True
            await bpInfoMessageLogic()

        if publicPerm or (await hasPermission(PermissionLvls.REACTION,message=message)):

            # equivalent of a /ping
            assert client.user is not None
            if client.user.mention in message.content:
                try:
                    await message.add_reaction(globalInfos.BOT_MENTIONED_REACTION)
                except discord.HTTPException:
                    pass

            # blueprint version reaction
            if not reactedToBPCodeInMsg:
                msgContent = await concatMsgContentAndAttachments(message.content,message.attachments)
                bpReactions = detectBPVersion(spz2.blueprints.getPotentialBPCodesInString(msgContent))
                if bpReactions is not None:
                    for reaction in bpReactions:
                        if isinstance(reaction,int):
                            reaction = client.get_emoji(reaction)
                            assert reaction is not None
                        try:
                            await message.add_reaction(reaction)
                        except discord.HTTPException:
                            pass

    @client.event
    async def on_interaction(interaction:discord.Interaction) -> None:
        if interaction.type != discord.InteractionType.component:
            return
        action = interaction.data["custom_id"]
        if action.startswith("antispam-"):
            await antispamAlertButtonInteraction(interaction,action.removeprefix("antispam-"))
        elif action == "accessBP":
            await bpInfoMessageButtonInteraction(interaction)
        else:
            assert interaction.message is not None
            await globalLogMessage(f"Unknown button action '{action}' for {interaction.message.jump_url}")

    @tree.error
    async def treeError(interaction:discord.Interaction,error:discord.app_commands.AppCommandError) -> None:
        assert error.__cause__ is not None
        await interactionErrorHandler(interaction,error.__cause__)

#endregion



#region owner commands

    @tree.command(name="stop",description=f"{globalInfos.OWNER_ONLY_BADGE} Stops the bot")
    async def stopCommand(interaction:discord.Interaction) -> None:
        if await hasPermission(PermissionLvls.OWNER,interaction=interaction):
            try:
                await interaction.response.send_message("Stopping bot",ephemeral=True)
            except Exception:
                print("Error while attempting to comfirm bot stopping")
            await client.close()
        else:
            if exitCommandWithoutResponse(interaction):
                return
            await interaction.response.send_message(globalInfos.NO_PERMISSION_TEXT,ephemeral=True)

    @tree.command(name="global-pause",description=f"{globalInfos.OWNER_ONLY_BADGE} Globally pauses the bot")
    async def globalPauseCommand(interaction:discord.Interaction) -> None:
        global globalPaused
        if await hasPermission(PermissionLvls.OWNER,interaction=interaction):
            globalPaused = True
            responseMsg = "Bot is now globally paused"
        else:
            if exitCommandWithoutResponse(interaction):
                return
            responseMsg = globalInfos.NO_PERMISSION_TEXT
        await interaction.response.send_message(responseMsg,ephemeral=True)

    @tree.command(name="global-unpause",description=f"{globalInfos.OWNER_ONLY_BADGE} Globally unpauses the bot")
    async def globalUnpauseCommand(interaction:discord.Interaction) -> None:
        global globalPaused
        if await hasPermission(PermissionLvls.OWNER,interaction=interaction):
            globalPaused = False
            responseMsg = "Bot is now globally unpaused"
        else:
            if exitCommandWithoutResponse(interaction):
                return
            responseMsg = globalInfos.NO_PERMISSION_TEXT
        await interaction.response.send_message(responseMsg,ephemeral=True)

#endregion



#region admin commands

    class RegisterCommandType:
        SINGLE_CHANNEL = "singleChannel"
        ROLE_LIST = "roleList"
        BOOL_VALUE = "boolValue"

    def registerAdminCommand(type_:str,cmdName:str,guildSettingsKey:str,cmdDesc:str="") -> None:

        if type_ == RegisterCommandType.SINGLE_CHANNEL:

            @tree.command(name=cmdName,description=f"{globalInfos.ADMIN_ONLY_BADGE} {cmdDesc}")
            @discord.app_commands.describe(channel="The channel. Don't provide this parameter to clear it")
            async def generatedChannelCommand(interaction:discord.Interaction,channel:discord.TextChannel|discord.Thread|None=None) -> None:
                if exitCommandWithoutResponse(interaction):
                    return
                if await hasPermission(PermissionLvls.ADMIN,interaction=interaction):
                    if channel is None:
                        setParamTo = None
                        responseMsgEnd = "cleared"
                    else:
                        setParamTo = channel.id
                        responseMsgEnd = f"set to {channel.mention}"
                    await guildSettings.setGuildSetting(interaction.guild_id,guildSettingsKey,setParamTo)
                    responseMsg = f"'{guildSettingsKey}' parameter {responseMsgEnd}"
                else:
                    responseMsg = globalInfos.NO_PERMISSION_TEXT
                await interaction.response.send_message(responseMsg,ephemeral=True)

        elif type_ == RegisterCommandType.BOOL_VALUE:

            @tree.command(name=cmdName,description=f"{globalInfos.ADMIN_ONLY_BADGE} {cmdDesc}")
            async def generatedBoolCommand(interaction:discord.Interaction,value:bool) -> None:
                if exitCommandWithoutResponse(interaction):
                    return
                if await hasPermission(PermissionLvls.ADMIN,interaction=interaction):
                    await guildSettings.setGuildSetting(interaction.guild_id,guildSettingsKey,value)
                    responseMsg = f"'{guildSettingsKey}' parameter has been set to {value}"
                else:
                    responseMsg = globalInfos.NO_PERMISSION_TEXT
                await interaction.response.send_message(responseMsg,ephemeral=True)

        elif type_ == RegisterCommandType.ROLE_LIST:

            @tree.command(name=cmdName,description=f"{globalInfos.ADMIN_ONLY_BADGE} Modifys the '{guildSettingsKey}' list")
            @discord.app_commands.describe(role="Only provide this if using 'add' or 'remove' subcommand")
            async def generatedRoleCommand(interaction:discord.Interaction,
                operation:typing.Literal["add","remove","view","clear"],role:discord.Role|None=None) -> None:
                if exitCommandWithoutResponse(interaction):
                    return
                if await hasPermission(PermissionLvls.ADMIN,interaction=interaction):

                    assert interaction.guild_id is not None
                    roleList = (await guildSettings.getGuildSettings(interaction.guild_id))[guildSettingsKey].copy()

                    if (operation in ("add","remove")) and (role is None):
                        responseMsg = "A role must be provided when using the 'add' or 'remove' subcommand"

                    elif operation == "add":

                        if len(roleList) >= globalInfos.MAX_ROLES_PER_LIST:
                            responseMsg = f"Can't have more than {globalInfos.MAX_ROLES_PER_LIST} roles per list"
                        else:
                            if role.id in roleList:
                                responseMsg = f"{role.mention} is already in the list"
                            else:
                                roleList.append(role.id)
                                await guildSettings.setGuildSetting(interaction.guild_id,guildSettingsKey,roleList)
                                responseMsg = f"Added {role.mention} to the '{guildSettingsKey}' list"

                    elif operation == "remove":

                        if role.id in roleList:
                            roleList.remove(role.id)
                            await guildSettings.setGuildSetting(interaction.guild_id,guildSettingsKey,roleList)
                            responseMsg = f"Removed {role.mention} from the '{guildSettingsKey}' list"
                        else:
                            responseMsg = "Role is not present in the list"

                    elif operation == "view":

                        roleList = [interaction.guild.get_role(r) for r in roleList]
                        if roleList== []:
                            responseMsg = "Empty list"
                        else:
                            responseMsg = "\n".join(f"- {role.mention} : {role.id}" for role in roleList)

                    elif operation == "clear":

                        await guildSettings.setGuildSetting(interaction.guild_id,guildSettingsKey,[])
                        responseMsg = f"'{guildSettingsKey}' list cleared"

                    else:
                        responseMsg = "Unknown operation"
                else:
                    responseMsg = globalInfos.NO_PERMISSION_TEXT
                await interaction.response.send_message(responseMsg,ephemeral=True)

        else:
            raise ValueError(f"Unknown type : '{type_}' in 'registerAdminCommand' function")

    registerAdminCommand(
        RegisterCommandType.SINGLE_CHANNEL,
        "restrict-to-channel",
        "restrictToChannel",
        "Restricts the use of the bot in public messages to one channel only"
    )

    registerAdminCommand(
        RegisterCommandType.SINGLE_CHANNEL,
        "set-antispam-alert-channel",
        "antispamAlertChannel",
        "Sets the channel for alerting when the antispam is triggered"
    )

    registerAdminCommand(
        RegisterCommandType.BOOL_VALUE,
        "restrict-to-roles-set-inverted",
        "restrictToRolesInverted",
        "Sets if the restrict to roles list should be inverted"
    )

    registerAdminCommand(
        RegisterCommandType.BOOL_VALUE,
        "set-paused",
        "paused",
        "Sets if the bot should be paused on this server"
    )

    registerAdminCommand(
        RegisterCommandType.BOOL_VALUE,
        "set-antispam-enabled",
        "antispamEnabled",
        "Sets if the antispam feature should be enabled on this server"
    )

    registerAdminCommand(RegisterCommandType.ROLE_LIST,"admin-roles","adminRoles")

    registerAdminCommand(RegisterCommandType.ROLE_LIST,"restrict-to-roles","restrictToRoles")

    @tree.command(name="usage-cooldown",description=f"{globalInfos.ADMIN_ONLY_BADGE} Sets the cooldown for usage of the bot publicly and privatley")
    @discord.app_commands.describe(cooldown="The cooldown in seconds")
    async def usageCooldownCommand(interaction:discord.Interaction,cooldown:int) -> None:
        if exitCommandWithoutResponse(interaction):
            return
        if await hasPermission(PermissionLvls.ADMIN,interaction=interaction):
            if cooldown < 0:
                responseMsg = "Cooldown value can't be negative"
            else:
                try:
                    datetime.timedelta(seconds=cooldown)
                except OverflowError:
                    responseMsg = "Cooldown value too big"
                else:
                    assert interaction.guild_id is not None
                    await guildSettings.setGuildSetting(interaction.guild_id,"usageCooldown",cooldown)
                    responseMsg = f"'usageCooldown' parameter has been set to {cooldown}"
        else:
            responseMsg = globalInfos.NO_PERMISSION_TEXT
        await interaction.response.send_message(responseMsg,ephemeral=True)

#endregion



#region public commands

    @tree.command(name="view-shapes",description="View shapes, useful if the bot says a shape code is invalid and you want to know why")
    @discord.app_commands.describe(message="The message like you would normally send it")
    async def viewShapesCommand(interaction:discord.Interaction,message:str) -> None:
        if exitCommandWithoutResponse(interaction):
            return
        await interaction.response.defer(ephemeral=True)
        if await hasPermission(PermissionLvls.PRIVATE_FEATURE,interaction=interaction):
            _, responseMsg, file = await useShapeViewer(message,True,interaction.user.id)
        else:
            responseMsg = globalInfos.NO_PERMISSION_TEXT
            file = None
        await interaction.followup.send(**getCommandResponse(responseMsg,file,interaction.guild,False))

    @tree.command(name="update-blueprint",description="Update a blueprint to the latest version")
    @discord.app_commands.describe(
        blueprint_code=globalInfos.SLASH_CMD_BP_CODE_PARAM_DESC,
        blueprint_file=globalInfos.SLASH_CMD_BP_FILE_PARAM_DESC
    )
    async def updateBlueprintCommand(
        interaction:discord.Interaction,
        blueprint_code:str|None=None,
        blueprint_file:discord.Attachment|None=None
    ) -> None:
        if exitCommandWithoutResponse(interaction):
            return

        async def runCommand() -> None:
            nonlocal responseMsg, noErrors

            await interaction.response.defer(ephemeral=True)

            if not await hasPermission(PermissionLvls.PRIVATE_FEATURE,interaction=interaction):
                responseMsg = globalInfos.NO_PERMISSION_TEXT
                return

            valid, errorOrBP = await getBPFromStringOrFile(blueprint_code,blueprint_file)
            if not valid:
                responseMsg = errorOrBP
                return

            try:
                responseMsg = spz2.blueprints.encodeBlueprint(spz2.blueprints.decodeBlueprint(errorOrBP,True))
                noErrors = True
            except spz2.blueprints.BlueprintError as e:
                responseMsg = f"Error happened : {e}"

        responseMsg = ""
        noErrors = False
        await runCommand()
        await interaction.followup.send(**getCommandResponse(
            responseMsg,
            None,
            interaction.guild,
            False,
            ("```","```") if noErrors else ("","")
        ))

    @tree.command(name="member-count",description="Display the number of members in this server")
    async def memberCountCommand(interaction:discord.Interaction) -> None:
        if exitCommandWithoutResponse(interaction):
            return

        def fillText(text:str,desiredLen:int,align:str) -> str:
            if align == "l":
                return text.ljust(desiredLen)
            if align == "r":
                return text.rjust(desiredLen)
            return text.center(desiredLen)

        async def runCommand() -> None:
            nonlocal responseMsg

            if not await hasPermission(PermissionLvls.PRIVATE_FEATURE,interaction=interaction):
                responseMsg = globalInfos.NO_PERMISSION_TEXT
                return

            if interaction.guild is None:
                responseMsg = "Not in a server"
                return

            guild = await client.fetch_guild(interaction.guild.id,with_counts=True)
            total = guild.approximate_member_count
            online = guild.approximate_presence_count
            assert total is not None
            assert online is not None
            offline = total - online
            totalTxt, onlineTxt, offlineTxt = "Total", "Online", "Offline"
            onlineProportion = online / total
            onlinePercent = round(onlineProportion*100)
            offlinePercent = 100-onlinePercent
            onlinePercent, offlinePercent = f"{onlinePercent}%", f"{offlinePercent}%"
            online, total, offline = [str(n) for n in (online,total,offline)]
            totalMaxLen = max(len(s) for s in (total,totalTxt))
            onlineMaxLen = max(len(s) for s in (online,onlinePercent,onlineTxt))
            offlineMaxLen = max(len(s) for s in (offline,offlinePercent,offlineTxt))
            numSpaces = 20
            totalLen = onlineMaxLen + numSpaces + totalMaxLen + numSpaces + offlineMaxLen
            spaces = " "*numSpaces
            filledProgressBar = round(onlineProportion*totalLen)
            lines = [
                f"{fillText(onlineTxt,onlineMaxLen,'l')}{spaces}{fillText(totalTxt,totalMaxLen,'c')}{spaces}{fillText(offlineTxt,offlineMaxLen,'r')}",
                f"{fillText(online,onlineMaxLen,'l')}{spaces}{fillText(total,totalMaxLen,'c')}{spaces}{fillText(offline,offlineMaxLen,'r')}",
                f"{fillText(onlinePercent,onlineMaxLen,'l')}{spaces}{' '*totalMaxLen}{spaces}{fillText(offlinePercent,offlineMaxLen,'r')}",
                f"{'#'*filledProgressBar}{'-'*(totalLen-filledProgressBar)}"
            ]
            responseMsg = "\n".join(lines)
            responseMsg = f"```{responseMsg}```"

        responseMsg = ""
        await runCommand()
        await interaction.response.send_message(responseMsg,ephemeral=True)

    @tree.command(name="operation-graph",description="See documentation on github")
    @discord.app_commands.describe(
        public="Errors will be sent publicly if this is True! Sets if the result is sent publicly in the channel",
        see_shape_vars="Whether or not to send the shape codes that were affected to every shape variable",
        spoiler="Whether or not to send the resulting image as spoiler",
        color_mode="The color mode to use for shapes",
        max_shape_layers="The maximum number of layers that shapes can have. In-game, 5 in insane and 4 otherwise"
    )
    @discord.app_commands.choices(color_mode=[
        discord.app_commands.Choice(name=cm.id,value=cm.id)
        for cm in spz2.ingameData.DEFAULT_COLOR_SCHEME.colorModes
    ])
    async def operationGraphCommand(
        interaction:discord.Interaction,
        instructions:str,
        public:bool=False,
        see_shape_vars:bool=False,
        spoiler:bool=False,
        color_mode:discord.app_commands.Choice[str]=spz2.ingameData.DEFAULT_COLOR_SCHEME.colorModes[0].id,
        max_shape_layers:int=4
    ) -> None:
        if exitCommandWithoutResponse(interaction):
            return

        async def runCommand() -> None:
            nonlocal responseMsg, file, imageSize

            if not await hasPermission(PermissionLvls.PUBLIC_FEATURE if public else PermissionLvls.PRIVATE_FEATURE,interaction=interaction):
                await interaction.response.defer(ephemeral=True)
                responseMsg = globalInfos.NO_PERMISSION_TEXT
                return

            await interaction.response.defer(ephemeral=not public)

            if max_shape_layers < 1:
                responseMsg = "Max shape layers must be at least 1"
                return

            valid, instructionsOrError = operationGraph.getInstructionsFromText(instructions)
            if not valid:
                responseMsg = instructionsOrError
                return

            valid, responseOrError = operationGraph.genOperationGraph(
                instructionsOrError,
                see_shape_vars,
                spz2.ingameData.DEFAULT_COLOR_SCHEME.colorModesById[color_mode if isinstance(color_mode,str) else color_mode.value],
                max_shape_layers
            )
            if not valid:
                responseMsg = responseOrError
                return

            (image, imageSize), shapeVarValues = responseOrError
            file = discord.File(image,"graph.png",spoiler=spoiler)
            if see_shape_vars:
                responseMsg = "\n".join(f"- {k} : {{{v.toShapeCode()}}}" for k,v in shapeVarValues.items())
            else:
                responseMsg = ""

        file:discord.File|None = None
        imageSize = 0
        responseMsg:str|utils.OutputString = ""
        await runCommand()
        if type(responseMsg) == utils.OutputString:
            responseMsg = responseMsg.render(public)
        await interaction.followup.send(**getCommandResponse(
            responseMsg,
            None if file is None else (file,imageSize),
            interaction.guild,
            public
        ))

    @tree.command(name="blueprint-info",description="Get infos about a blueprint")
    @discord.app_commands.describe(
        blueprint_code=globalInfos.SLASH_CMD_BP_CODE_PARAM_DESC,
        blueprint_file=globalInfos.SLASH_CMD_BP_FILE_PARAM_DESC,
        advanced="Whether or not to get extra infos about the blueprint"
    )
    async def blueprintInfoCommand(
        interaction:discord.Interaction,
        blueprint_code:str|None=None,
        blueprint_file:discord.Attachment|None=None,
        advanced:bool=False
    ) -> None:
        if exitCommandWithoutResponse(interaction):
            return

        async def runCommand() -> None:
            nonlocal responseMsg

            await interaction.response.defer(ephemeral=True)

            if not await hasPermission(PermissionLvls.PRIVATE_FEATURE,interaction=interaction):
                responseMsg = globalInfos.NO_PERMISSION_TEXT
                return

            valid, errorOrBP = await getBPFromStringOrFile(blueprint_code,blueprint_file)
            if not valid:
                responseMsg = errorOrBP
                return

            try:
                decodedBP = spz2.blueprints.decodeBlueprint(errorOrBP)
            except spz2.blueprints.BlueprintError as e:
                responseMsg = f"Error while decoding blueprint : {e}"
                return

            responseMsg = getBPInfoText(decodedBP,advanced)

        responseMsg = ""
        await runCommand()
        await interaction.followup.send(**getCommandResponse(responseMsg,None,interaction.guild,False))

    # @tree.command(name="research-viewer",description="View the research tree")
    # @discord.app_commands.describe(
    #     level="The level to view, starting from 1",
    #     node="The node to view, starting from 1. The 'level' parameter must be set to a value",
    #     public="Errors will be sent publicly if this is True! Sets if the result is sent publicly in the channel"
    # )
    # async def researchViewerCommand(interaction:discord.Interaction,level:int=0,node:int=0,public:bool=False) -> None:
    #     if exitCommandWithoutResponse(interaction):
    #         return

    #     async def runCommand() -> None:
    #         nonlocal responseMsg, file, fileSize
    #         file = None

    #         if not await hasPermission(PermissionLvls.PUBLIC_FEATURE if public else PermissionLvls.PRIVATE_FEATURE,interaction=interaction):
    #             await interaction.response.defer(ephemeral=True)
    #             responseMsg = globalInfos.NO_PERMISSION_TEXT
    #             return

    #         await interaction.response.defer(ephemeral=not public)
    #         if level < 0 or level > len(spz2.research.reserachTree):
    #             responseMsg = "Error : invalid level"
    #             return

    #         if node != 0:

    #             if level == 0:
    #                 responseMsg = "Error : 'node' parameter provided but not 'level' parameter"
    #                 return

    #             curLevel = spz2.research.reserachTree[level-1]
    #             if node < 1 or node > len(curLevel.sideGoals)+1:
    #                 responseMsg = "Error : invalid node"
    #                 return

    #             file, fileSize = researchViewer.renderNode(level-1,node-1)
    #             curNode = curLevel.milestone if node == 1 else curLevel.sideGoals[node-2]
    #             desc = utils.decodedFormatToDiscordFormat(utils.decodeUnityFormat(curNode.desc))
    #             desc = "\n".join(f"> {l}" for l in desc.split("\n"))
    #             if curNode.unlocks == []:
    #                 unlocks = "<Nothing>"
    #             else:
    #                 unlocks = ", ".join(f"`{u}`" for u in curNode.unlocks)

    #             lines = [
    #                 f"- **Name** : {utils.decodedFormatToDiscordFormat(utils.decodeUnityFormat(curNode.title))}",
    #                 f"- **Id** : `{curNode.id}`",
    #                 f"- **Description** :\n{desc}",
    #                 f"- **Goal Shape** : `{curNode.goalShape}` x{utils.sepInGroupsNumber(curNode.goalAmount)}",
    #                 f"- **Unlocks** :\n> {unlocks}",
    #                 f"- **Lock/Unlock commands** :",
    #                 f"> ```research.set {curNode.id} 0```",
    #                 f"> ```research.set {curNode.id} 1```"
    #             ]

    #             responseMsg = "\n".join(lines)
    #             return

    #         if level != 0:
    #             file, fileSize = researchViewer.renderLevel(level-1)
    #             responseMsg = ""
    #             return

    #         file, fileSize = researchViewer.renderTree()
    #         responseMsg = ""

    #     responseMsg:str; fileSize:int
    #     await runCommand()
    #     if file is not None:
    #         file = discord.File(file,"researchTree.png")
    #     await interaction.followup.send(**getCommandResponse(responseMsg,None if file is None else (file,fileSize),interaction.guild,public))

    @tree.command(name="msg",description="Public by default ! A command for shortcuts to messages")
    @discord.app_commands.describe(
        msg="The message id",
        public="Whether to send the message publicly or not"
    )
    @discord.app_commands.choices(msg=[discord.app_commands.Choice(name=id,value=id) for id in msgCommandMessages.keys()])
    async def msgCommand(interaction:discord.Interaction,msg:discord.app_commands.Choice[str],public:bool=True) -> None:
        if exitCommandWithoutResponse(interaction):
            return
        if await hasPermission(PermissionLvls.PUBLIC_FEATURE if public else PermissionLvls.PRIVATE_FEATURE,interaction=interaction):
            curMsgId = msg.value
            curCooldownKey = (interaction.guild_id,curMsgId)
            curTime = getCurrentTime()
            curCooldownValue = msgCommandCooldownLastTriggered.get(curCooldownKey)
            if (
                (curCooldownValue is not None)
                and ((curTime-curCooldownValue) < datetime.timedelta(seconds=globalInfos.MSG_COMMAND_COOLDOWN_SECONDS))
            ):
                responseMsg = "This message is in cooldown"
                ephemeral = True
            else:
                msgCommandCooldownLastTriggered[curCooldownKey] = curTime
                responseMsg = msgCommandMessages[curMsgId]
                ephemeral = not public
        else:
            responseMsg = globalInfos.NO_PERMISSION_TEXT
            ephemeral = True
        if not ephemeral:
            responseMsg = safenString(responseMsg)
        await interaction.response.send_message(responseMsg,ephemeral=ephemeral)

    @tree.command(name="blueprint-creator",description="Create blueprints")
    @discord.app_commands.describe(
        to_create="What blueprint to create, see docs on github for specifics",
        extra="Extra data potentially required depending on the 'to_create' parameter"
    )
    async def blueprintCreatorCommand(
        interaction:discord.Interaction,
        to_create:typing.Literal[
            "item-producer-w-shape",
            "all-buildings",
            "all-platforms"
        ],
        extra:str=""
    ) -> None:
        if exitCommandWithoutResponse(interaction):
            return

        async def runCommand() -> None:
            nonlocal responseMsg, noErrors

            await interaction.response.defer(ephemeral=True)

            if not await hasPermission(PermissionLvls.PRIVATE_FEATURE,interaction=interaction):
                responseMsg = globalInfos.NO_PERMISSION_TEXT
                return

            if to_create.startswith("item-producer-w-"):

                if extra == "":
                    responseMsg = "This requires the 'extra' parameter to be set to a value"
                    return

                errorMsg, result = shapeCodeGenerator.generateShapeCodes(extra)

                if result is None:
                    responseMsg = f"Invalid shape code : {errorMsg}"
                    return
                shapes,_ = result

                shapesLen = len(shapes)
                if shapesLen != 1:
                    responseMsg = f"Not exactly one shape returned ({shapesLen})"
                    return

                buildingExtra = spz2.blueprintsExtraData.ItemProducerExtraData(
                    spz2.blueprintsExtraData.ShapeGenerator(
                        spz2.blueprintsExtraData.ShapeGeneratorType.shape,
                        shapes[0]
                    )
                )

                try:
                    responseMsg = spz2.blueprints.encodeBlueprint(spz2.blueprints.Blueprint(
                        spz2.blueprints.BuildingBlueprint([spz2.blueprints.BuildingEntry(
                            spz2.utils.Pos(0,0),
                            spz2.utils.Rotation(0),
                            spz2.buildings.allBuildingInternalVariants["SandboxItemProducerDefaultInternalVariant"],
                            buildingExtra
                        )])
                    ))
                    noErrors = True
                except spz2.blueprints.BlueprintError as e:
                    responseMsg = f"Error happened while creating blueprint : {e}"
                return

            toCreateBuildings = to_create.removeprefix("all-") == "buildings"
            toPlaceList = (
                spz2.buildings.allBuildingInternalVariants.values()
                if toCreateBuildings else
                spz2.islands.allIslands.values()
            )
            curX = 0
            entryList = []

            for toPlace in toPlaceList:
                curTiles = toPlace.tiles
                if not toCreateBuildings:
                    curTiles = [t.pos for t in curTiles]
                minX = min(t.x for t in curTiles)
                minZ = min(t.z for t in curTiles)
                maxX = max(t.x for t in curTiles)
                curX -= minX
                entryList.append((
                    spz2.blueprints.BuildingEntry
                    if toCreateBuildings else
                    spz2.blueprints.IslandEntry
                )(
                    spz2.utils.Pos(curX,0,-minZ),
                    spz2.utils.Rotation(0),
                    toPlace
                ))
                curX += maxX + 1

            try:
                responseMsg = spz2.blueprints.encodeBlueprint(spz2.blueprints.Blueprint((
                        spz2.blueprints.BuildingBlueprint
                        if toCreateBuildings else
                        spz2.blueprints.IslandBlueprint
                    )(
                        entryList
                    )
                ))
                noErrors = True
            except spz2.blueprints.BlueprintError as e:
                responseMsg = f"Error happened while creating blueprint : {e}"

        responseMsg = ""
        noErrors = True
        await runCommand()
        await interaction.followup.send(**getCommandResponse(
            responseMsg,
            None,
            interaction.guild,
            False,
            ("```","```") if noErrors else ("","")
        ))

    @tree.command(name="access-blueprint",description="Access a blueprint")
    @discord.app_commands.describe(
        blueprint_code=globalInfos.SLASH_CMD_BP_CODE_PARAM_DESC,
        blueprint_file=globalInfos.SLASH_CMD_BP_FILE_PARAM_DESC
    )
    async def accessBlueprintCommand(
        interaction:discord.Interaction,
        blueprint_code:str|None=None,
        blueprint_file:discord.Attachment|None=None
    ) -> None:

        await accessBlueprintCommandInnerPart(interaction,getBPFromStringOrFile(blueprint_code,blueprint_file))

    @tree.context_menu(name="access-blueprint")
    async def accessBlueprintContextMenu(interaction:discord.Interaction,message:discord.Message):
        await accessBlueprintCommandFromMessage(interaction,message)

#endregion



    try:
        with open(globalInfos.TOKEN_PATH) as f:
            token = f.read()
    except FileNotFoundError:
        token = os.getenv(globalInfos.TOKEN_ENV_VAR)
        if token is None:
            raise Exception("Couldn't find token from file or environement variable")
    client.run(token)

executedOnReady = False
globalPaused = False
msgCommandMessages:dict[str,str]
class antiSpamLastMessagesType(typing.TypedDict):
    content:str
    messages:list[discord.Message]
    count:int
    timestamp:datetime.datetime
antiSpamLastMessages:dict[tuple[int,int],antiSpamLastMessagesType] = {}
usageCooldownLastTriggered:dict[tuple[int,int|None],datetime.datetime] = {}
msgCommandCooldownLastTriggered:dict[tuple[int|None,str],datetime.datetime] = {}
class shapeViewerLastErrorsType(typing.TypedDict):
    count:int
    timestamp:datetime.datetime
shapeViewerLastErrors:dict[int,shapeViewerLastErrorsType] = {}