import os
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = ""

import responses
import globalInfos
import blueprints
import operationGraph
import utils
import gameInfos
import researchViewer
import guildSettings
import shapeCodeGenerator
import autoMessages
import shapeViewer

import discord
import json
import sys
import traceback
import io
import typing
import datetime

async def globalLogMessage(message:str) -> None:
    if globalInfos.GLOBAL_LOG_CHANNEL is None:
        print(message)
    else:
        logChannel = client.get_channel(globalInfos.GLOBAL_LOG_CHANNEL)
        await logChannel.send(**getCommandResponse(message,None,logChannel.guild,True,("```","```")))

async def globalLogError() -> None:
    await globalLogMessage(("".join(traceback.format_exception(*sys.exc_info())))[:-1])

async def useShapeViewer(userMessage:str,sendErrors:bool) -> tuple[bool,str,tuple[discord.File,int]|None]:
    try:

        response = responses.handleResponse(userMessage)
        msgParts = []
        hasErrors = False
        file = None

        if response is None:
            if sendErrors:
                msgParts.append("No potential shape codes detected")

        else:
            response, hasInvalid, errorMsgs = response

            if hasInvalid:
                hasErrors = True
                if sendErrors:
                    msgParts.append("**Error messages :**\n"+"\n".join(f"- {msg}" for msg in errorMsgs))

            if response is not None:

                (image, imageSize), spoiler, resultingShapeCodes, viewer3dLinks = response
                file = discord.File(image,"shapes.png",spoiler=spoiler)
                if resultingShapeCodes is not None:
                    msgParts.append(
                        "**Resulting shape codes :**\n"+
                        "\n".join(
                            " ".join(f"{{{code}}}" for code in codeGroup)
                            for codeGroup in discord.utils.as_chunks(resultingShapeCodes,globalInfos.SHAPES_PER_ROW)
                        )
                    )
                if viewer3dLinks is not None:
                    msgParts.append(
                        "**3D viewer links :**\n"+
                        "\n".join(
                            " ".join(f"{{{link}}}" for link in linkGroup)
                            for linkGroup in discord.utils.as_chunks(viewer3dLinks,globalInfos.SHAPES_PER_ROW)
                        )
                    )

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
            userRoles = message.author.roles[1:]
            adminPerm = message.author.guild_permissions.administrator

    elif interaction is not None:

        userId = interaction.user.id
        channelId = interaction.channel_id
        guildId = interaction.guild_id
        if interaction.guild is not None:
            userRoles = interaction.user.roles[1:]
            if interaction.is_user_integration(): # potentially a bodge bug fix
                adminPerm = False
            else:
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

def detectBPVersion(potentialBPCodes:list[str]) -> list[str|int]|None:

    versions = []

    for bp in potentialBPCodes:

        try:
            version = blueprints.getBlueprintVersion(bp)
        except blueprints.BlueprintError:
            continue

        versionReaction = gameInfos.versions.versionNumToReactions(version)

        if versionReaction is None:
            continue

        versions.append(versionReaction)

    if len(versions) != 1:
        return None

    return versions[0]

def safenString(string:str) -> str:
    return discord.utils.escape_mentions(string)

async def getBPFromStringOrFile(string:str|None,file:discord.Attachment|None) -> str|None:
    if file is None:
        toReturn = string
    else:
        toReturn = await decodeAttachment(file)
        if toReturn is None:
            return None
    return toReturn.strip()

def getCommandResponse(text:str,file:tuple[discord.File,int]|None,guild:discord.Guild|None,public:bool,
    notInFileFormat:tuple[str,str]=("","")) -> dict[str,str|discord.File]:
    kwargs = {}

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

# port of sbe's antispam feature with difference of being separated per server and possiblity of sending an alert when triggered
async def antiSpam(message:discord.Message) -> None|bool:

    async def sendAlert() -> None:

        curAlertChannel = curGuildSettings["antispamAlertChannel"]
        if curAlertChannel is None:
            return

        curAlertChannel = client.get_channel(curAlertChannel)
        if curAlertChannel is None:
            return

        alertMsg = f"{message.author.mention} triggered the antispam :"
        msgContentFile = msgToFile(msgContent,"messageContent.txt",curAlertChannel.guild)
        if msgContentFile is None:
            alertMsg += " <couldn't put message content in a file>"

        await curAlertChannel.send(alertMsg,file=msgContentFile)

    global antiSpamLastMessages

    if globalPaused:
        return

    if message.author.bot:
        return

    if message.guild is None:
        return

    curGuildSettings = await guildSettings.getGuildSettings(message.guild.id)

    if not curGuildSettings["antispamEnabled"]:
        return

    userId = message.author.id
    guildId = message.guild.id
    curGuildMember = (userId,guildId)
    msgContent = message.content
    curTime = getCurrentTime()

    for guildMember in list(antiSpamLastMessages.keys()):
        if (curTime - antiSpamLastMessages[guildMember]["timestamp"]) > datetime.timedelta(seconds=globalInfos.ANTISPAM_TIME_INTERVAL_SECONDS):
            antiSpamLastMessages.pop(guildMember)

    curInfo = antiSpamLastMessages.get(curGuildMember)
    if (curInfo is not None) and (curInfo["content"] == msgContent):
        curInfo["messages"].append(message)
        curInfo["count"] += 1
        curInfo["timestamp"] = curTime

        if curInfo["count"] >= globalInfos.ANTISPAM_MSG_COUNT_TRESHOLD:
            messages:list[discord.Message] = curInfo["messages"]
            curInfo["messages"] = []

            if not message.author.is_timed_out():
                try:

                    await message.author.timeout(
                        datetime.timedelta(seconds=globalInfos.ANTISPAM_TIMEOUT_SECONDS),
                        reason=f"antispam: {msgContent}" # seems like no errors happen if the reason string is more than the 512 char limit in discord's UI
                    )

                    for msg in messages: # port difference : only delete if permission to timeout
                        await msg.delete()

                except (discord.Forbidden,discord.NotFound):
                    pass

                else:
                    await sendAlert()
                    return True
        return

    newInfo = {
        "content" : msgContent,
        "messages" : [message],
        "count" : 1,
        "timestamp" : curTime
    }
    antiSpamLastMessages[curGuildMember] = newInfo

async def concatMsgContentAndAttachments(content:str,attachments:list[discord.Attachment]) -> str:
    for file in attachments:
        fileContent = await decodeAttachment(file)
        if fileContent is None:
            continue
        content += fileContent
    return content

def getBPInfoText(blueprint:blueprints.Blueprint,advanced:bool) -> str:

    def formatCounts(bp:blueprints.BuildingBlueprint|blueprints.IslandBlueprint|None,name:str) -> str:
        output = f"\n**{name} counts :**\n"
        if bp is None:
            output += "None"
        else:
            if type(bp) == blueprints.BuildingBlueprint:
                counts = bp.getBuildingCounts()
                lines = []
                for iv,bc in gameInfos.buildings.getCategorizedBuildingCounts(counts).items():
                    lines.append(f"- `{gameInfos.buildings.allInternalVariantLists[iv].title}` : `{utils.sepInGroupsNumber(sum(bc.values()))}`")
                    for b,c in bc.items():
                        lines.append(f"  - `{b}` : `{utils.sepInGroupsNumber(c)}`")
                output += "\n".join(lines)
            else:
                counts = bp.getIslandCounts()
                output += "\n".join(f"- `{gameInfos.islands.allIslands[k].title}` : `{utils.sepInGroupsNumber(v)}`" for k,v in counts.items())
        return output

    versionTxt = gameInfos.versions.versionNumToText(blueprint.version,advanced)
    if versionTxt is None:
        versionTxt = "Unknown"
    elif advanced:
        versionTxt = f"[{', '.join(f'`{txt}`' for txt in versionTxt)}]"
    else:
        versionTxt = f"`{versionTxt}`"
    bpTypeTxt = "Platform" if blueprint.type == blueprints.ISLAND_BP_TYPE else "Building"
    try:
        bpCost = f"`{utils.sepInGroupsNumber(blueprint.getCost())}`"
    except blueprints.BlueprintError:
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
            f"Platform size : `{islandSize.width}`x`{islandSize.height}`",
            f"Platform tiles : `{utils.sepInGroupsNumber(blueprint.islandBP.getTileCount())}`"
        ])

    blueprintIcons = blueprint.buildingBP.icons if blueprint.type == blueprints.BUILDING_BP_TYPE else blueprint.islandBP.icons
    blueprintIconsStr = []
    for icon in blueprintIcons:
        if icon.type == "empty":
            blueprintIconsStr.append("<empty>")
        elif icon.type == "icon":
            blueprintIconsStr.append(f"`{icon.value}`")
        else:
            blueprintIconsStr.append(f"{{{icon.value}}}")

    responseParts.append([
        f"Icons : {', '.join(blueprintIconsStr)}"
    ])

    finalOutput = "\n".join(", ".join(part) for part in responseParts)

    if advanced:
        finalOutput += formatCounts(blueprint.buildingBP,"Building")
        finalOutput += formatCounts(blueprint.islandBP,"Platform")

    return finalOutput

async def accessBlueprintCommandInnerPart(
    interaction:discord.Interaction,
    getBPCode:typing.Callable[[],typing.Coroutine[typing.Any,typing.Any,tuple[str,bool]]]
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

        toProcessBlueprint, bpCodeValid = await getBPCode()
        if not bpCodeValid:
            responseMsg = toProcessBlueprint
            return

        try:
            decodedBP = blueprints.decodeBlueprint(toProcessBlueprint)
        except blueprints.BlueprintError as e:
            responseMsg = f"Error while decoding blueprint : {e}"
            return

        infoText = getBPInfoText(decodedBP,False)
        infoText = "\n".join(f"> {l}" for l in infoText.split("\n"))

        bpCodeLinkSafe = toProcessBlueprint
        for old,new in globalInfos.LINK_CHAR_REPLACEMENT.items():
            bpCodeLinkSafe = bpCodeLinkSafe.replace(old,new)
        bpCode3dViewLink = f"{globalInfos.BLUEPRINT_3D_VIEWER_LINK_START}{bpCodeLinkSafe}"

        responseMsg = "\n".join([
            "**Blueprint Infos :**",
            infoText,
            "**Actions :**",
            f"> [[View in 3D]](<{bpCode3dViewLink}>)"
        ])

        fileTooBig = False
        toCreateFiles:list[tuple[str,str]] = []

        if len(responseMsg) > globalInfos.MESSAGE_MAX_LENGTH:
            toCreateFiles.append((infoText,"blueprint infos.txt"))
            toCreateFiles.append((bpCode3dViewLink,"3D viewer link.txt"))
            responseMsg = ""

        toCreateFiles.append((toProcessBlueprint,"blueprint.txt"))
        toCreateFiles.append((toProcessBlueprint,"blueprint.spz2bp"))

        for fileContent,fileName in toCreateFiles:
            file = msgToFile(fileContent,fileName,interaction.guild)
            if file is None:
                fileTooBig = True
            else:
                files.append(file)

        if fileTooBig:
            files.append(discord.File(globalInfos.FILE_TOO_BIG_PATH))

    responseMsg:str; files:list[discord.File]
    await inner()
    await interaction.followup.send(responseMsg,files=files)

##################################################

def runDiscordBot() -> None:

    global client, msgCommandMessages

    client = discord.Client(intents=discord.Intents.all(),activity=discord.Game("shapez 2"))
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
    async def on_message(message:discord.Message) -> None:
        try:

            if message.author == client.user:
                return

            if (await antiSpam(message)) is True:
                return

            publicPerm = await hasPermission(PermissionLvls.PUBLIC_FEATURE,message=message)
            if publicPerm:

                # shape viewer
                hasErrors, responseMsg, file = await useShapeViewer(message.content,False)
                if hasErrors:
                    await message.add_reaction(globalInfos.INVALID_SHAPE_CODE_REACTION)
                if (responseMsg != "") or (file is not None):
                    await message.channel.send(**getCommandResponse(responseMsg,file,message.guild,True))

                # automatic messages
                autoMsgResult = await autoMessages.checkMessage(message)
                if autoMsgResult != []:
                    responseMsg = "\n".join(autoMsgResult)
                    try:
                        await message.reply(safenString(responseMsg),mention_author=False)
                    except discord.HTTPException: # error raised when og message was deleted
                        pass

            if publicPerm or (await hasPermission(PermissionLvls.REACTION,message=message)):

                # equivalent of a /ping
                if globalInfos.BOT_ID in (user.id for user in message.mentions):
                    await message.add_reaction(globalInfos.BOT_MENTIONED_REACTION)

                # blueprint version reaction
                msgContent = await concatMsgContentAndAttachments(message.content,message.attachments)
                bpReactions = detectBPVersion(blueprints.getPotentialBPCodesInString(msgContent))
                if bpReactions is not None:
                    for reaction in bpReactions:
                        if type(reaction) == int:
                            reaction = client.get_emoji(reaction)
                        await message.add_reaction(reaction)

        except Exception:
            await globalLogError()

    @tree.error
    async def on_error(interaction:discord.Interaction,error:discord.app_commands.AppCommandError) -> None:
        await globalLogError()
        responseMsg = f"{globalInfos.UNKNOWN_ERROR_TEXT} ({error.__cause__.__class__.__name__})"
        if interaction.response.is_done():
            await interaction.followup.send(responseMsg)
        else:
            await interaction.response.send_message(responseMsg,ephemeral=True)

    # owner only commands

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

    # admin only commands

    class RegisterCommandType:
        SINGLE_CHANNEL = "singleChannel"
        ROLE_LIST = "roleList"
        BOOL_VALUE = "boolValue"

    def registerAdminCommand(type_:str,cmdName:str,guildSettingsKey:str,cmdDesc:str="") -> None:

        if type_ == RegisterCommandType.SINGLE_CHANNEL:

            @tree.command(name=cmdName,description=f"{globalInfos.ADMIN_ONLY_BADGE} {cmdDesc}")
            @discord.app_commands.describe(channel="The channel. Don't provide this parameter to clear it")
            async def generatedCommand(interaction:discord.Interaction,channel:discord.TextChannel|discord.Thread|None=None) -> None:
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
            async def generatedCommand(interaction:discord.Interaction,value:bool) -> None:
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
            async def generatedCommand(interaction:discord.Interaction,
                operation:typing.Literal["add","remove","view","clear"],role:discord.Role|None=None) -> None:
                if exitCommandWithoutResponse(interaction):
                    return
                if await hasPermission(PermissionLvls.ADMIN,interaction=interaction):

                    roleList = (await guildSettings.getGuildSettings(interaction.guild_id))[guildSettingsKey]

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
                    await guildSettings.setGuildSetting(interaction.guild_id,"usageCooldown",cooldown)
                    responseMsg = f"'usageCooldown' parameter has been set to {cooldown}"
        else:
            responseMsg = globalInfos.NO_PERMISSION_TEXT
        await interaction.response.send_message(responseMsg,ephemeral=True)

    # public commands

    @tree.command(name="view-shapes",description="View shapes, useful if the bot says a shape code is invalid and you want to know why")
    @discord.app_commands.describe(message="The message like you would normally send it")
    @discord.app_commands.allowed_installs(guilds=True,users=True)
    async def viewShapesCommand(interaction:discord.Interaction,message:str) -> None:
        if exitCommandWithoutResponse(interaction):
            return
        await interaction.response.defer(ephemeral=True)
        if await hasPermission(PermissionLvls.PRIVATE_FEATURE,interaction=interaction):
            _, responseMsg, file = await useShapeViewer(message,True)
        else:
            responseMsg = globalInfos.NO_PERMISSION_TEXT
            file = None
        await interaction.followup.send(**getCommandResponse(responseMsg,file,interaction.guild,False))

    @tree.command(name="change-blueprint-version",description="Change a blueprint's version")
    @discord.app_commands.describe(
        blueprint=globalInfos.SLASH_CMD_BP_PARAM_DESC,
        version=f"The blueprint version number (latest public : {gameInfos.versions.LATEST_PUBLIC_GAME_VERSION}, latest patreon only : {gameInfos.versions.LATEST_GAME_VERSION})",
        blueprint_file=globalInfos.SLASH_CMD_BP_FILE_PARAM_DESC,
        advanced="Whether or not to fully decode and encode the blueprint"
    )
    @discord.app_commands.allowed_installs(guilds=True,users=True)
    async def changeBlueprintVersionCommand(
        interaction:discord.Interaction,
        blueprint:str,
        version:int,
        blueprint_file:discord.Attachment|None=None,
        advanced:bool=False
    ) -> None:
        if exitCommandWithoutResponse(interaction):
            return

        async def runCommand() -> None:
            nonlocal responseMsg, noErrors
            noErrors = False

            if not await hasPermission(PermissionLvls.PRIVATE_FEATURE,interaction=interaction):
                responseMsg = globalInfos.NO_PERMISSION_TEXT
                return

            toProcessBlueprint = await getBPFromStringOrFile(blueprint,blueprint_file)
            if toProcessBlueprint is None:
                responseMsg = "Error while processing file"
                return

            try:
                if advanced:
                    decodedBP = blueprints.decodeBlueprint(toProcessBlueprint)
                    decodedBP.version = version
                    responseMsg = blueprints.encodeBlueprint(decodedBP)
                else:
                    responseMsg = blueprints.changeBlueprintVersion(toProcessBlueprint,version)
                noErrors = True
            except blueprints.BlueprintError as e:
                responseMsg = f"Error happened : {e}"

        responseMsg:str; noErrors:bool
        await runCommand()
        await interaction.response.send_message(ephemeral=True,**getCommandResponse(responseMsg,None,interaction.guild,False,
            ("```","```") if noErrors else ("","")))

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

            guild = await client.fetch_guild(interaction.guild_id,with_counts=True)
            total = guild.approximate_member_count
            online = guild.approximate_presence_count
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

        responseMsg:str
        await runCommand()
        await interaction.response.send_message(responseMsg,ephemeral=True)

    @tree.command(name="operation-graph",description="See documentation on github")
    @discord.app_commands.describe(
        public="Errors will be sent publicly if this is True! Sets if the result is sent publicly in the channel",
        see_shape_vars="Whether or not to send the shape codes that were affected to every shape variable",
        spoiler="Whether or not to send the resulting image as spoiler",
        color_skin="The color skin to use for shapes"
    )
    @discord.app_commands.allowed_installs(guilds=True,users=True)
    async def operationGraphCommand(
        interaction:discord.Interaction,
        instructions:str,
        public:bool=False,
        see_shape_vars:bool=False,
        spoiler:bool=False,
        color_skin:shapeViewer.EXTERNAL_COLOR_SKINS_ANNOTATION=shapeViewer.EXTERNAL_COLOR_SKINS[0]
    ) -> None:
        if exitCommandWithoutResponse(interaction):
            return

        async def runCommand() -> None:
            nonlocal responseMsg, file, imageSize
            file = None

            if not await hasPermission(PermissionLvls.PUBLIC_FEATURE if public else PermissionLvls.PRIVATE_FEATURE,interaction=interaction):
                await interaction.response.defer(ephemeral=True)
                responseMsg = globalInfos.NO_PERMISSION_TEXT
                return

            await interaction.response.defer(ephemeral=not public)
            valid, instructionsOrError = operationGraph.getInstructionsFromText(instructions)
            if not valid:
                responseMsg = instructionsOrError
                return

            valid, responseOrError = operationGraph.genOperationGraph(instructionsOrError,see_shape_vars,color_skin)
            if not valid:
                responseMsg = responseOrError
                return

            (image, imageSize), shapeVarValues = responseOrError
            file = discord.File(image,"graph.png",spoiler=spoiler)
            if see_shape_vars:
                responseMsg = "\n".join(f"- {k} : {{{v}}}" for k,v in shapeVarValues.items())
            else:
                responseMsg = ""

        file:discord.File; imageSize:int
        await runCommand()
        if type(responseMsg) == utils.OutputString:
            responseMsg = responseMsg.render(public)
        await interaction.followup.send(**getCommandResponse(responseMsg,None if file is None else (file,imageSize),interaction.guild,public))

    @tree.command(name="blueprint-info",description="Get infos about a blueprint")
    @discord.app_commands.describe(
        blueprint=globalInfos.SLASH_CMD_BP_PARAM_DESC,
        advanced="Whether or not to get extra infos about the blueprint",
        blueprint_file=globalInfos.SLASH_CMD_BP_FILE_PARAM_DESC
    )
    @discord.app_commands.allowed_installs(guilds=True,users=True)
    async def blueprintInfoCommand(
        interaction:discord.Interaction,
        blueprint:str,
        advanced:bool=False,
        blueprint_file:discord.Attachment|None=None
    ) -> None:
        if exitCommandWithoutResponse(interaction):
            return

        async def runCommand() -> None:
            nonlocal responseMsg

            if not await hasPermission(PermissionLvls.PRIVATE_FEATURE,interaction=interaction):
                responseMsg = globalInfos.NO_PERMISSION_TEXT
                return

            toProcessBlueprint = await getBPFromStringOrFile(blueprint,blueprint_file)
            if toProcessBlueprint is None:
                responseMsg = "Error while processing file"
                return

            try:
                decodedBP = blueprints.decodeBlueprint(toProcessBlueprint)
            except blueprints.BlueprintError as e:
                responseMsg = f"Error while decoding blueprint : {e}"
                return

            responseMsg = getBPInfoText(decodedBP,advanced)

        responseMsg:str
        await runCommand()
        await interaction.response.send_message(ephemeral=True,**getCommandResponse(responseMsg,None,interaction.guild,False))

    @tree.command(name="research-viewer",description="View the research tree")
    @discord.app_commands.describe(
        level="The level to view, starting from 1",
        node="The node to view, starting from 1. The 'level' parameter must be set to a value",
        public="Errors will be sent publicly if this is True! Sets if the result is sent publicly in the channel"
    )
    async def researchViewerCommand(interaction:discord.Interaction,level:int=0,node:int=0,public:bool=False) -> None:
        if exitCommandWithoutResponse(interaction):
            return

        async def runCommand() -> None:
            nonlocal responseMsg, file, fileSize
            file = None

            if not await hasPermission(PermissionLvls.PUBLIC_FEATURE if public else PermissionLvls.PRIVATE_FEATURE,interaction=interaction):
                await interaction.response.defer(ephemeral=True)
                responseMsg = globalInfos.NO_PERMISSION_TEXT
                return

            await interaction.response.defer(ephemeral=not public)
            if level < 0 or level > len(gameInfos.research.reserachTree):
                responseMsg = "Error : invalid level"
                return

            if node != 0:

                if level == 0:
                    responseMsg = "Error : 'node' parameter provided but not 'level' parameter"
                    return

                curLevel = gameInfos.research.reserachTree[level-1]
                if node < 1 or node > len(curLevel.sideGoals)+1:
                    responseMsg = "Error : invalid node"
                    return

                file, fileSize = researchViewer.renderNode(level-1,node-1)
                curNode = curLevel.milestone if node == 1 else curLevel.sideGoals[node-2]
                desc = utils.decodedFormatToDiscordFormat(utils.decodeUnityFormat(curNode.desc))
                desc = "\n".join(f"> {l}" for l in desc.split("\n"))
                if curNode.unlocks == []:
                    unlocks = "<Nothing>"
                else:
                    unlocks = ", ".join(f"`{u}`" for u in curNode.unlocks)

                lines = [
                    f"- **Name** : {utils.decodedFormatToDiscordFormat(utils.decodeUnityFormat(curNode.title))}",
                    f"- **Id** : `{curNode.id}`",
                    f"- **Description** :\n{desc}",
                    f"- **Goal Shape** : `{curNode.goalShape}` x{utils.sepInGroupsNumber(curNode.goalAmount)}",
                    f"- **Unlocks** :\n> {unlocks}",
                    f"- **Lock/Unlock commands** :",
                    f"> ```research.set {curNode.id} 0```",
                    f"> ```research.set {curNode.id} 1```"
                ]

                responseMsg = "\n".join(lines)
                return

            if level != 0:
                file, fileSize = researchViewer.renderLevel(level-1)
                responseMsg = ""
                return

            file, fileSize = researchViewer.renderTree()
            responseMsg = ""

        responseMsg:str; fileSize:int
        await runCommand()
        if file is not None:
            file = discord.File(file,"researchTree.png")
        await interaction.followup.send(**getCommandResponse(responseMsg,None if file is None else (file,fileSize),interaction.guild,public))

    @tree.command(name="msg",description="Public by default ! A command for shortcuts to messages")
    @discord.app_commands.describe(
        msg="The message id",
        public="Whether to send the message publicly or not"
    )
    @discord.app_commands.choices(msg=[discord.app_commands.Choice(name=id,value=id) for id in msgCommandMessages.keys()])
    @discord.app_commands.allowed_installs(guilds=True,users=True)
    async def msgCommand(interaction:discord.Interaction,msg:discord.app_commands.Choice[str],public:bool=True) -> None:
        if exitCommandWithoutResponse(interaction):
            return
        if await hasPermission(PermissionLvls.PUBLIC_FEATURE if public else PermissionLvls.PRIVATE_FEATURE,interaction=interaction):
            responseMsg = msgCommandMessages[msg.value]
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
    @discord.app_commands.allowed_installs(guilds=True,users=True)
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
            nonlocal responseMsg, noErrors, to_create
            noErrors = False

            if not await hasPermission(PermissionLvls.PRIVATE_FEATURE,interaction=interaction):
                responseMsg = globalInfos.NO_PERMISSION_TEXT
                return

            blueprintInfos:tuple[int,int] = (
                gameInfos.versions.LATEST_MAJOR_VERSION,
                gameInfos.versions.LATEST_GAME_VERSION
            )

            if to_create.startswith("item-producer-w-"):

                if extra == "":
                    responseMsg = "This requires the 'extra' parameter to be set to a value"
                    return

                to_create = to_create.removeprefix("item-producer-w-")

                shapeCodesOrError, valid = shapeCodeGenerator.generateShapeCodes(extra)

                if not valid:
                    responseMsg = f"Invalid shape code : {shapeCodesOrError}"
                    return

                shapeCodesLen = len(shapeCodesOrError)
                if shapeCodesLen != 1:
                    responseMsg = f"Not exactly one shape code returned ({shapeCodesLen})"
                    return

                buildingExtra = {"type":"shape","value":shapeCodesOrError[0]}

                try:
                    responseMsg = blueprints.encodeBlueprint(blueprints.Blueprint(
                        *blueprintInfos,
                        blueprints.BUILDING_BP_TYPE,
                        blueprints.BuildingBlueprint([blueprints.BuildingEntry(
                            utils.Pos(0,0),
                            utils.Rotation(0),
                            gameInfos.buildings.allBuildings["SandboxItemProducerDefaultInternalVariant"],
                            buildingExtra
                        )],blueprints.getDefaultBlueprintIcons(blueprints.BUILDING_BP_TYPE))
                    ))
                    noErrors = True
                except blueprints.BlueprintError as e:
                    responseMsg = f"Error happened while creating blueprint : {e}"
                return

            to_create = to_create.removeprefix("all-")
            toCreateBuildings = to_create == "buildings"
            toPlaceList = (
                gameInfos.buildings.allBuildings.values()
                if toCreateBuildings else
                gameInfos.islands.allIslands.values()
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
                shared:tuple[utils.Pos,utils.Rotation,gameInfos.buildings.Building|gameInfos.islands.Island,None] = (
                    utils.Pos(curX,0,-minZ),utils.Rotation(0),toPlace,None)
                if toCreateBuildings:
                    entryList.append(blueprints.BuildingEntry(*shared))
                else:
                    entryList.append(blueprints.IslandEntry(*shared,None))
                curX += maxX + 1

            bpType = blueprints.BUILDING_BP_TYPE if toCreateBuildings else blueprints.ISLAND_BP_TYPE
            try:
                responseMsg = blueprints.encodeBlueprint(blueprints.Blueprint(
                    *blueprintInfos,
                    bpType,
                    (blueprints.BuildingBlueprint if toCreateBuildings else blueprints.IslandBlueprint)
                    (entryList,blueprints.getDefaultBlueprintIcons(bpType))
                ))
                noErrors = True
            except blueprints.BlueprintError as e:
                responseMsg = f"Error happened while creating blueprint : {e}"

        responseMsg:str; noErrors:bool
        await runCommand()
        await interaction.response.send_message(ephemeral=True,**getCommandResponse(responseMsg,None,interaction.guild,False,
            ("```","```") if noErrors else ("","")))

    @tree.command(name="access-blueprint",description="Access a blueprint")
    @discord.app_commands.describe(
        blueprint=globalInfos.SLASH_CMD_BP_PARAM_DESC,
        blueprint_file=globalInfos.SLASH_CMD_BP_FILE_PARAM_DESC
    )
    @discord.app_commands.allowed_installs(guilds=True,users=True)
    async def accessBlueprintCommand(
        interaction:discord.Interaction,
        blueprint:str,
        blueprint_file:discord.Attachment|None=None
    ) -> None:

        async def getBPCode() -> tuple[str,bool]:
            toProcessBlueprint = await getBPFromStringOrFile(blueprint,blueprint_file)
            if toProcessBlueprint is None:
                return "Error while processing blueprint file",False
            return toProcessBlueprint,True

        await accessBlueprintCommandInnerPart(interaction,getBPCode)

    @tree.context_menu(name="access-blueprint")
    @discord.app_commands.allowed_installs(guilds=True,users=True)
    async def accessBlueprintContextMenu(interaction:discord.Interaction,message:discord.Message):

        async def getBPCode() -> tuple[str,bool]:
            potentialBPCodes = blueprints.getPotentialBPCodesInString(
                await concatMsgContentAndAttachments(message.content,message.attachments)
            )
            if len(potentialBPCodes) != 1:
                return "Message doesn't contain exactly one blueprint code",False
            return potentialBPCodes[0],True

        await accessBlueprintCommandInnerPart(interaction,getBPCode)

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
antiSpamLastMessages:dict[tuple[int,int],dict[str,str|list[discord.Message]|int|datetime.datetime]] = {}
usageCooldownLastTriggered:dict[tuple[int,int|None],datetime.datetime] = {}