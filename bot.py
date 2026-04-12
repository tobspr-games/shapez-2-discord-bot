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
import enum
import aiohttp



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
                "**Resulting shape codes :**\n"
                + "\n".join(
                    " ".join(f"{{{code}}}" for code in row)
                    for row in renderResult["shapeCodes"]
                )
            )

        if renderResult["viewer3dLinks"] is not None:
            msgParts.append(
                "**3D viewer links :**\n"
                + "\n".join(
                    " ".join(f"{{{link}}}" for link in row)
                    for row in renderResult["viewer3dLinks"]
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
        await interaction.followup.send(responseMsg,ephemeral=True) # ephemeral required for button interactions
    else:
        await interaction.response.send_message(responseMsg,ephemeral=True)

class AntispamAlertButtons(discord.ui.View):

    REASON_MSG = "Request by moderator from antispam alert"

    def __init__(
        self,
        userId:int,
        thresholdLevel:typing.Literal["l","h"],
        buttonStates:str="1111"
    ):
        super().__init__()
        customIdTemplate = f"antispam-{{0}}-{userId}-{buttonStates}-{thresholdLevel}"
        self.add_item(discord.ui.Button(
            label = "Send info DM",
            style = discord.ButtonStyle.blurple,
            custom_id = customIdTemplate.format("sendDM"),
            disabled = buttonStates[0] == "0"
        ))
        self.add_item(discord.ui.Button(
            label = "Un-timeout",
            style = discord.ButtonStyle.green,
            custom_id = customIdTemplate.format("untimeout"),
            disabled = buttonStates[1] == "0"
        ))
        self.add_item(discord.ui.Button(
            label = "Kick",
            style = discord.ButtonStyle.red,
            custom_id = customIdTemplate.format("kick"),
            disabled = buttonStates[2] == "0"
        ))
        self.add_item(discord.ui.Button(
            label = "Ban",
            style = discord.ButtonStyle.red,
            custom_id = customIdTemplate.format("ban"),
            disabled = buttonStates[3] == "0"
        ))
        thresholdName = {"l":"low","h":"high"}[thresholdLevel]
        self.add_item(discord.ui.Button(
            label = f"Threshold used : {thresholdName}",
            style = discord.ButtonStyle.grey,
            disabled = True
        ))

async def antispamAlertButtonInteraction(interaction:discord.Interaction,rawAction:str) -> None:

    action, userId, buttonStates, thresholdLevel = rawAction.split("-")
    assert interaction.guild is not None
    assert interaction.message is not None
    userIdInt = int(userId)
    interactingUserPerms = interaction.channel.permissions_for(interaction.user)

    try:
        user = await interaction.guild.fetch_member(userIdInt)
    except (discord.Forbidden,discord.NotFound):
        user = None

    disableIndexes = []
    if user is None:
        responseMsg = "Couldn't find user"

    elif action == "sendDM":
        try:
            await user.send(globalInfos.ANTISPAM_DM_MSG)
            responseMsg = "Succesfully sent DM"
            disableIndexes = [0]
        except discord.Forbidden:
            responseMsg = "Failed to send DM"

    elif action == "untimeout":
        if interactingUserPerms.moderate_members:
            try:
                await user.timeout(None,reason=AntispamAlertButtons.REASON_MSG)
                responseMsg = "Succesfully un-timed out user"
                disableIndexes = [1]
            except (discord.Forbidden,discord.NotFound):
                responseMsg = "Failed to un-timeout user"
        else:
            responseMsg = globalInfos.NO_PERMISSION_TEXT

    elif action == "kick":
        if interactingUserPerms.kick_members:
            try:
                await user.kick(reason=AntispamAlertButtons.REASON_MSG)
                responseMsg = "Succesfully kicked user"
                disableIndexes = list(range(4))
            except (discord.Forbidden,discord.NotFound):
                responseMsg = "Failed to kick user"
        else:
            responseMsg = globalInfos.NO_PERMISSION_TEXT

    elif action == "ban":
        if interactingUserPerms.ban_members:
            try:
                await user.ban(delete_message_days=0,reason=AntispamAlertButtons.REASON_MSG)
                responseMsg = "Succesfully banned user"
                disableIndexes = list(range(4))
            except (discord.Forbidden,discord.NotFound):
                responseMsg = "Failed to ban user"
        else:
            responseMsg = globalInfos.NO_PERMISSION_TEXT

    else:
        raise ValueError(f"Unknown antispam action : {action}")

    await interaction.response.send_message(responseMsg,ephemeral=True)
    buttonStates = "".join("0" if i in disableIndexes else state for i,state in enumerate(buttonStates))
    await interaction.message.edit(view=AntispamAlertButtons(userIdInt,thresholdLevel,buttonStates))

# modified version of sbe's antispam
async def antiSpam(message:discord.Message) -> typing.Literal[True]|None:

    async def sendAlert() -> None:

        curAlertChannel = curGuildSettings["antispamAlertChannel"]
        if curAlertChannel is None:
            return

        curAlertChannel = client.get_channel(curAlertChannel)
        if not isinstance(curAlertChannel,(discord.TextChannel,discord.Thread)):
            return

        alertMsg = f"{message.author.mention} triggered the antispam "
        kwargs = {}
        if len(alertMsgContents) == 0:
            alertMsg += "(attachment-only message)"
        else:
            msgContentsFile = msgToFile(alertMsgContents,"messageContents.txt",curAlertChannel.guild)
            if msgContentsFile is None:
                alertMsg += "(couldn't put message content in a file)"
            else:
                kwargs["file"] = msgContentsFile
                alertMsg += ":"

        await curAlertChannel.send(alertMsg,view=AntispamAlertButtons(message.author.id,thresholdName),**kwargs)

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

    # remove messages that are too old
    curTime = getCurrentTime()
    for guildMember in list(antiSpamLastMessages.keys()):
        if (
            (curTime - antiSpamLastMessages[guildMember]["messages"][-1].created_at)
            > datetime.timedelta(seconds=globalInfos.ANTISPAM_TIME_INTERVAL_SECONDS)
        ):
            antiSpamLastMessages.pop(guildMember)

    if len(message.content) == 0:
        msgContent = b""
        for att in message.attachments:
            if att.width is None:
                continue
            if att.size > globalInfos.MAX_DOWNLOAD_IMAGE_FILE_SIZE:
                continue
            try:
                msgContent += await att.read()
            except (discord.HTTPException,discord.NotFound):
                pass
    else:
        msgContent = message.content

    # if no text and no images
    if len(msgContent) == 0:
        return

    curGuildMember = (message.author.id,message.guild.id)
    msgChannelId = message.channel.id
    curInfo = antiSpamLastMessages.get(curGuildMember)

    if curInfo is None:
        newInfo:antiSpamLastMessagesType = {
            "messages" : [message],
            "contents" : {msgChannelId : [msgContent]}
        }
        antiSpamLastMessages[curGuildMember] = newInfo
        return

    # reset to latest message if the content hasn't been seen in another channel
    # where other messages have already been posted
    for contentsChannelId,contents in curInfo["contents"].items():
        if msgChannelId == contentsChannelId:
            continue
        if msgContent not in contents:
            curInfo["messages"] = [message]
            curInfo["contents"] = {msgChannelId : [msgContent]}
            return

    # keep track of the current message and its content
    curInfo["messages"].append(message)
    if curInfo["contents"].get(msgChannelId) is None:
        curInfo["contents"][msgChannelId] = [msgContent]
    else:
        curInfo["contents"][msgChannelId].append(msgContent)

    highThreshold = True

    # if the member joined recently
    if (
        isinstance(message.author,discord.Member)
        and (message.author.joined_at is not None)
        and (
            (curTime-message.author.joined_at)
            < datetime.timedelta(hours=globalInfos.ANTISPAM_NEW_MEMBER_PERIOD_HOURS)
        )
    ):
        highThreshold = False

    # the first channel is guaranteed to have all message contents
    allContents = list(curInfo["contents"].values())[0]

    # if the message content is short
    # and thus more likely to be legitimately repeated
    if any(len(c) < 10 for c in allContents):
        highThreshold = True

    # if there are only images and no text
    if all(isinstance(c,bytes) for c in allContents):
        highThreshold = False

    # if there are "forbidden" words
    for content in allContents:
        if not isinstance(content,str):
            continue
        if any(s in content for s in ("@everyone","@here")):
            highThreshold = False
            break

    threshold, thresholdName = (
        (globalInfos.ANTISPAM_CHANNEL_COUNT_THRESHOLD_HIGH,"h")
        if highThreshold else
        (globalInfos.ANTISPAM_CHANNEL_COUNT_THRESHOLD_LOW,"l")
    )

    if len(curInfo["contents"]) < threshold:
        return

    if (isinstance(message.author,discord.User)) or (message.author.is_timed_out()):
        return

    alertMsgContents = "\n\n===== ShapeBot 2 separator =====\n\n".join(
        c for c in allContents if isinstance(c,str)
    )

    try:
        await message.author.timeout(
            datetime.timedelta(seconds=globalInfos.ANTISPAM_TIMEOUT_SECONDS),
            reason=f"antispam: {alertMsgContents}"
        )
    except discord.Forbidden:
        await globalLogMessage(f"Failed to timeout {message.author.id} for antispam")
        return # don't delete messages and don't send an alert

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
    getBPCode:typing.Coroutine[typing.Any,typing.Any,tuple[bool,str]],
    manualLoadingText:bool,
    doubleRef:bool|None
) -> None:
    if exitCommandWithoutResponse(interaction):
        return

    async def inner() -> None:
        nonlocal responseMsg, files

        if manualLoadingText:
            await interaction.response.send_message("Loading...",ephemeral=True)
        else:
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

        if (doubleRef is not None) and (decodedBP.version < spz2.versions.LATEST_GAME_VERSION):
            kwargs["view"] = UpdateBPMessageButton(doubleRef)

    responseMsg = ""
    files = []
    kwargs = {}
    await inner()
    if manualLoadingText:
        await interaction.edit_original_response(content=responseMsg,attachments=files,**kwargs)
    else:
        await interaction.followup.send(responseMsg,files=files,**kwargs)

async def getSinglePotentialBPCodeInMessage(message:discord.Message) -> str|None:
    potentialBPCodes = spz2.blueprints.getPotentialBPCodesInString(
        await concatMsgContentAndAttachments(message.content,message.attachments)
    )
    if len(potentialBPCodes) != 1:
        return None
    return potentialBPCodes[0]

async def accessBlueprintCommandFromMessage(
    interaction:discord.Interaction,
    message:discord.Message,
    manualLoadingText:bool,
    doubleRef:bool
) -> None:

    async def getBPCode() -> tuple[bool,str]:
        potentialBPCode = await getSinglePotentialBPCodeInMessage(message)
        if potentialBPCode is None:
            return False, "Message doesn't contain exactly one blueprint code"
        return True, potentialBPCode

    await accessBlueprintCommandInnerPart(interaction,getBPCode(),manualLoadingText,doubleRef)

class BPInfoMessageButton(discord.ui.View):
    def __init__(self):
        super().__init__()
        self.add_item(discord.ui.Button(
            label = "View in 3D / Convert file format",
            style = discord.ButtonStyle.grey,
            custom_id = "accessBP"
        ))

async def getMessageReply(message:discord.Message) -> discord.Message|None:
    if message.type != discord.MessageType.reply:
        return None
    msgRef = message.reference
    if msgRef is None:
        return None
    if msgRef.message_id is None:
        return None
    if isinstance(msgRef.resolved,discord.DeletedReferencedMessage):
        return None
    if msgRef.resolved is not None:
        return msgRef.resolved
    try:
        return await message.channel.fetch_message(msgRef.message_id)
    except discord.NotFound:
        return None

async def bpInfoMessageButtonInteraction(interaction:discord.Interaction) -> None:
    assert interaction.message is not None
    message = await getMessageReply(interaction.message)
    if message is None:
        await interaction.response.send_message("Can't access original message",ephemeral=True)
    else:
        await accessBlueprintCommandFromMessage(interaction,message,True,True)

async def pinMsgToPos(
    message:discord.Message,
    pos:int,
    channel:discord.abc.Messageable,
    user:discord.User
) -> tuple[bool,str]:

    pos -= 1
    allPins = [m async for m in channel.pins(limit=None)]
    moveMsgs = allPins[:pos]
    reasonMsg = f"Request from {user.name}"

    try:

        for msg in moveMsgs:
            await msg.unpin(reason=reasonMsg)

        await message.pin(reason=reasonMsg)

        for msg in reversed(moveMsgs):
            await msg.pin(reason=reasonMsg)

    except discord.Forbidden:
        return False,"No permission to manage pins"

    return True,""

async def parseMessageId(messageId:str,channel:discord.abc.Messageable) -> str|discord.Message:
    if len(messageId) > 25:
        return "Message ID too long"
    try:
        messageIdInt = int(messageId)
    except ValueError:
        return "Message ID not an integer"
    if messageIdInt < 0:
        return "Message ID can't be negative"
    try:
        return await channel.fetch_message(messageIdInt)
    except discord.Forbidden:
        return "I can't read messages in this channel"
    except discord.NotFound:
        return "Message not found"

class UpdateBPMessageButton(discord.ui.View):
    def __init__(self,doubleRef:bool):
        super().__init__()
        self.add_item(discord.ui.Button(
            label = "Update blueprint to the latest version",
            style = discord.ButtonStyle.blurple,
            custom_id = f"updateBP{"2" if doubleRef else "1"}"
        ))

async def updateBPMessageButtonInteraction(interaction:discord.Interaction,doubleRef:bool) -> None:

    assert interaction.message is not None
    await interaction.response.send_message("Loading...",ephemeral=True)

    async def inner() -> tuple[bool,str]:

        if doubleRef:

            bpInfoMessage = await getMessageReply(interaction.message)
            if bpInfoMessage is None:
                return False, "Can't access blueprint info message"

            bpMessage = await getMessageReply(bpInfoMessage)
            if bpMessage is None:
                return False, "Can't access original message"

        else:

            metadata = interaction.message.interaction_metadata
            assert metadata is not None

            if metadata.target_message is None:
                msgId = metadata.target_message_id
                assert msgId is not None
                try:
                    bpMessage = await interaction.channel.fetch_message(msgId)
                except discord.NotFound:
                    return False, "Can't access original message"
            else:
                bpMessage = metadata.target_message

        potentialBP = await getSinglePotentialBPCodeInMessage(bpMessage)
        if potentialBP is None:
            return False, "Message doesn't contain exactly one blueprint code"

        return updateBPLogic(potentialBP)

    noErrors, responseMsg = await inner()
    kwargs = getCommandResponse(
        responseMsg,
        None,
        interaction.guild,
        False,
        ("```","```") if noErrors else ("","")
    )
    if "file" in kwargs:
        kwargs["attachments"] = [kwargs.pop("file")]
    if "content" not in kwargs:
        kwargs["content"] = None
    await interaction.edit_original_response(**kwargs)

def updateBPLogic(blueprint:str) -> tuple[bool,str]:
    try:
        return True, spz2.blueprints.encodeBlueprint(spz2.blueprints.decodeBlueprint(blueprint,True))
    except spz2.blueprints.BlueprintError as e:
        return False, f"Error happened : {e}"

#endregion



#region events

def runDiscordBot() -> None:

    global client, msgCommandMessages

    intents = discord.Intents.all()
    intents.presences = False
    client = discord.Client(intents=intents,activity=discord.Game("shapez 2"))
    tree = discord.app_commands.CommandTree(client)

    try:
        with open(globalInfos.SECRETS_PATH) as f:
            secrets = json.load(f)
        botToken = secrets["bot_token"]
        susUsersToken = secrets["sus_users_token"]
        susUsersEndpoint = secrets["sus_users_endpoint"]
    except FileNotFoundError:
        botToken = os.getenv(globalInfos.BOT_TOKEN_ENV_VAR)
        susUsersToken = os.getenv(globalInfos.SUS_USERS_TOKEN_ENV_VAR)
        susUsersEndpoint = os.getenv(globalInfos.SUS_USERS_ENDPOINT_ENV_VAR)
        if (botToken is None) or (susUsersToken is None) or (susUsersEndpoint is None):
            raise Exception("Couldn't find secrets from file or environement variable")

    with open(globalInfos.MSG_COMMAND_MESSAGES_PATH,encoding="utf-8") as f:
        msgCommandMessages = json.load(f)

    async def susUsersRequest(method:typing.Literal["get","put","delete"],path:str) -> tuple[bool,typing.Any]:

        async with aiohttp.ClientSession(
            susUsersEndpoint,
            headers = {"Authorization" : f"Bearer {susUsersToken}"}
        ) as session:

            if method == "get":
                func = session.get
            elif method == "put":
                func = session.put
            elif method == "delete":
                func = session.delete
            else:
                raise ValueError

            async with func(path) as response:

                content = await response.json()

                if response.status == 200:
                    return True, content

                await globalLogMessage(f"Failed sus users request ({response.status}) : {method} '{path}' {content}")
                return False, None

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
                await message.add_reaction(client.get_emoji(globalInfos.INVALID_SHAPE_CODE_REACTION))
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
                        view=BPInfoMessageButton()
                    )
                except discord.HTTPException:
                    return
                reactedToBPCodeInMsg = True
            await bpInfoMessageLogic()

        reactionPerm = publicPerm or (await hasPermission(PermissionLvls.REACTION,message=message))
        if reactionPerm:

            # equivalent of a /ping
            assert client.user is not None
            if client.user.mention in message.content:
                try:
                    await message.add_reaction(client.get_emoji(globalInfos.BOT_MENTIONED_REACTION))
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

        # sus users
        if (
            (message.type == discord.MessageType.new_member)
            and (
                reactionPerm
                or (await hasPermission(PermissionLvls.PRIVATE_FEATURE,message=message))
            )
        ):
            success, response = await susUsersRequest("delete",str(message.author.id))
            if success:
                assert response.get("success") is True

    @client.event
    async def on_interaction(interaction:discord.Interaction) -> None:
        if interaction.type != discord.InteractionType.component:
            return
        action = interaction.data["custom_id"]
        if action.startswith("antispam-"):
            await antispamAlertButtonInteraction(interaction,action.removeprefix("antispam-"))
        elif action == "accessBP":
            await bpInfoMessageButtonInteraction(interaction)
        elif action in ("updateBP1","updateBP2"):
            await updateBPMessageButtonInteraction(interaction,action[-1] == "2")
        else:
            assert interaction.message is not None
            await globalLogMessage(f"Unknown button action '{action}' for {interaction.message.jump_url}")

    @client.event
    async def on_member_join(member:discord.Member) -> None:
        success, response = await susUsersRequest("put",str(member.id))
        if success:
            assert response.get("success") is True

    @client.event
    async def on_raw_member_remove(payload:discord.RawMemberRemoveEvent) -> None:
        # no errors if the user wasn't in the list
        success, response = await susUsersRequest("delete",str(payload.user.id))
        if success:
            assert response.get("success") is True

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

    class RegisterCommandType(enum.Enum):
        SINGLE_CHANNEL = "singleChannel"
        ROLE_LIST = "roleList"
        BOOL_VALUE = "boolValue"

    def registerAdminCommand(type_:RegisterCommandType,cmdName:str,guildSettingsKey:str,cmdDesc:str="") -> None:

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

    @tree.command(name="pin-msg",description=f"{globalInfos.ADMIN_ONLY_BADGE} Pins a message to the given position")
    @discord.app_commands.describe(
        message_id="ID of the message to pin",
        position="Where to put the message in the pins list, 1-indexed"
    )
    async def pinMsgCommand(interaction:discord.Interaction,message_id:str,position:int) -> None:
        if exitCommandWithoutResponse(interaction):
            return

        await interaction.response.defer(ephemeral=True)

        async def runCommand() -> None:
            nonlocal responseMsg

            if not await hasPermission(PermissionLvls.ADMIN,interaction=interaction):
                responseMsg = globalInfos.NO_PERMISSION_TEXT
                return

            if position < 1:
                responseMsg = "'position' must be at least 1"
                return

            message = await parseMessageId(message_id,interaction.channel)

            if isinstance(message,str):
                responseMsg = message
                return

            if message.pinned:
                responseMsg = "Message is already pinned"
                return

            success, responseMsg = await pinMsgToPos(
                message,
                position,
                interaction.channel,
                interaction.user
            )
            if success:
                responseMsg = "Successfully pinned message"

        responseMsg = ""
        await runCommand()
        await interaction.followup.send(responseMsg)

    @tree.command(name="move-pinned-msg",description=f"{globalInfos.ADMIN_ONLY_BADGE} Moves a pinned message to the given position")
    @discord.app_commands.describe(
        from_position="The position in the pins list of the message to move, 1-indexed",
        to_position="Where to move the message in the pins list, 1-indexed"
    )
    async def movePinnedMsgCommand(interaction:discord.Interaction,from_position:int,to_position:int) -> None:
        if exitCommandWithoutResponse(interaction):
            return

        await interaction.response.defer(ephemeral=True)

        async def runCommand() -> None:
            nonlocal responseMsg, from_position

            if not await hasPermission(PermissionLvls.ADMIN,interaction=interaction):
                responseMsg = globalInfos.NO_PERMISSION_TEXT
                return

            if from_position < 1:
                responseMsg = "'from_position' must be at least 1"
                return
            if to_position < 1:
                responseMsg = "'to_position' must be at least 1"
                return
            if from_position == to_position:
                responseMsg = "'from' and 'to' positions can't be the same"
                return

            allPins = [m async for m in interaction.channel.pins(limit=None)]
            from_position -= 1

            if from_position >= len(allPins):
                responseMsg = "'from_position' is too big"
                return

            message = allPins[from_position]

            try:
                await message.unpin(reason=f"Request from {interaction.user.name}")
            except discord.Forbidden:
                responseMsg = "No permission to manage pins"
                return

            success, responseMsg = await pinMsgToPos(
                message,
                to_position,
                interaction.channel,
                interaction.user
            )
            if success:
                responseMsg = "Successfully moved message"

        responseMsg = ""
        await runCommand()
        await interaction.followup.send(responseMsg)

    @tree.command(name="sus-users",description=f"{globalInfos.ADMIN_ONLY_BADGE} View users that don't have a join message")
    async def susUsersCommand(interaction:discord.Interaction) -> None:
        if exitCommandWithoutResponse(interaction):
            return
        await interaction.response.defer(ephemeral=True)
        if await hasPermission(PermissionLvls.ADMIN,interaction=interaction):
            success, response = await susUsersRequest("get","")
            if success:
                users:list[dict[str,str]] = response
                if len(users) == 0:
                    responseMsg = "No sus users"
                else:
                    responseMsg = " ".join(f"<@{u["userId"]}>" for u in users)
            else:
                responseMsg = "Database request failed"
        else:
            responseMsg = globalInfos.NO_PERMISSION_TEXT
        await interaction.followup.send(**getCommandResponse(responseMsg,None,interaction.guild,False))

    @tree.command(name="remove-sus-user",description=f"{globalInfos.ADMIN_ONLY_BADGE} Manually mark the specified user as not sus")
    async def susUsersCommand(interaction:discord.Interaction,user:discord.User) -> None:
        if exitCommandWithoutResponse(interaction):
            return
        await interaction.response.defer(ephemeral=True)
        if await hasPermission(PermissionLvls.ADMIN,interaction=interaction):
            success, response = await susUsersRequest("delete",str(user.id))
            if success:
                assert response.get("success") is True
                responseMsg = f"{user.mention} removed from the sus users list"
            else:
                responseMsg = "Database request failed"
        else:
            responseMsg = globalInfos.NO_PERMISSION_TEXT
        await interaction.followup.send(**getCommandResponse(responseMsg,None,interaction.guild,False))

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

            noErrors, responseMsg = updateBPLogic(errorOrBP)

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

        await accessBlueprintCommandInnerPart(
            interaction,
            getBPFromStringOrFile(blueprint_code,blueprint_file),
            False,
            None
        )

    @tree.context_menu(name="access-blueprint")
    async def accessBlueprintContextMenu(interaction:discord.Interaction,message:discord.Message) -> None:
        await accessBlueprintCommandFromMessage(interaction,message,False,False)

    @tree.command(name="find-replies",description="Finds replies to a given message")
    @discord.app_commands.describe(message_id="Look for replies to the message with this ID")
    async def findRepliesCommand(interaction:discord.Interaction,message_id:str) -> None:
        if exitCommandWithoutResponse(interaction):
            return

        async def runCommand() -> None:
            nonlocal responseMsg

            await interaction.response.defer(ephemeral=True)

            if not await hasPermission(PermissionLvls.PRIVATE_FEATURE,interaction=interaction):
                responseMsg = globalInfos.NO_PERMISSION_TEXT
                return

            assert isinstance(interaction.channel,discord.abc.Messageable)

            message = await parseMessageId(message_id,interaction.channel)
            if isinstance(message,str):
                responseMsg = message
                return

            replies:list[discord.Message] = []

            async for msg in message.channel.history(
                limit=None,
                before=message.created_at + datetime.timedelta(hours=24),
                after=message
            ):
                if (await getMessageReply(msg)) == message:
                    replies.append(msg)

            if len(replies) == 0:
                responseMsg = "Couldn't find any replies"
            else:
                responseMsg = "\n".join(f"- {m.jump_url}" for m in replies)

        responseMsg = ""
        await runCommand()
        await interaction.followup.send(**getCommandResponse(responseMsg,None,interaction.guild,False))

#endregion



    client.run(botToken)

executedOnReady = False
globalPaused = False
msgCommandMessages:dict[str,str]
class antiSpamLastMessagesType(typing.TypedDict):
    messages:list[discord.Message]
    contents:dict[int,list[str|bytes]]
antiSpamLastMessages:dict[tuple[int,int],antiSpamLastMessagesType] = {}
usageCooldownLastTriggered:dict[tuple[int,int|None],datetime.datetime] = {}
msgCommandCooldownLastTriggered:dict[tuple[int|None,str],datetime.datetime] = {}
class shapeViewerLastErrorsType(typing.TypedDict):
    count:int
    timestamp:datetime.datetime
shapeViewerLastErrors:dict[int,shapeViewerLastErrorsType] = {}