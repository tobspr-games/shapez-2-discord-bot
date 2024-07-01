## 01 Jul 24
- Switch to using Pillow instead of pygame

- Heroku specific changes :
  - Add `Procfile`, `requirements.txt`, `runtime.txt`
  - Remove `.dockerignore`, `Dockerfile`
  - Make token and guild settings able to use environment variables if files for them aren't found

- Make guild settings hardcoded

- Remove user install support

## 30 Jun 24
- Fix error when decoding island blueprint containing buildings
- Fix error when using /blueprint-creator item-producer-w-shape
- Fix blueprint being of incorrect type internally when using /blueprint-creator all-platforms

## 29 Jun 24
- Add /msg commands

## 28 Jun 24
- Update for alphas : 22.3, 22.4, 22.4-wiretest-1 :
  - Add versions in game infos
  - Update buildings, islands, translations
  - Update blueprints :
    - Make `$type` key mandatory
    - Make additional data required for train related platforms
    - Make no additional data be a single `\x00` byte
    - Add support for blueprint icons
- Upgrade to discord.py 2.4.0
- Add user install support for some commands
- Make 'copy-from' function in translation strings able to load strings that haven't been parsed yet
- Make translation string objects use the components from after the 'copy-from' function has been used

## 17 Jun 24
- Update for alpha 22.2 :
  - Add version in game infos
  - Update buildings, islands and translations in game infos
  - Update space belts, pipes and rails additional data support in blueprints
  - Add train loaders, unloaders, stops and producers additional data support in blueprints
  - Allow strings to be shorter than their indicated length in blueprints additional data
  - Change 'windmill' to 'diamond' in readme and /msg all-shapes
- Add /msg play
- Add text and image file download size limit
- Replace `except Exception`s with more precise errors when the errors that can happen are documented
- Remove unneeded string to bytes conversion in blueprint decoding
- Use constants for building and island IDs in blueprints additional data
- Fix incorrect advanced blueprint info formatting

## 13 Jun 24
- Make latest game version constant dynamically generated based on the game versions constant
- Upgrade to discord.py 2.3.2
- Set 'restrict to guilds' global infos constant
- Update /msg all-shapes screenshot
- Remove /access-blueprint message support and move that functionality to a message context menu command

## 04 Jun 24
- Update for alphas : 21, 21.1 :
  - Add versions in game infos
  - Update buildings :
    - Remove variant lists :
      - Update extract game infos script
      - Update buildings module in game infos
      - Update /blueprint-info with advanced=true response formatting
  - Update islands
  - Add translations extraction in extract game infos script
- Use constant from builtin string module for digit strings in utils
- Make antispam not take effect when global paused

## 25 May 24
- Update for alpha 20 :
  - Add version in game infos
  - Add game translations support in game infos
  - Update buildings and islands in game infos
    - Move building and island titles from JSON files to being generated with translations module with possibility of override in JSON files
  - Update colorblind shapes support to color skin support :
    - Update shape viewer
    - Add string diplay parameter type in responses module
    - Change /cb display parameter to /colors
    - Change /operation-graph 'colorblind' parameter to 'color_skin'
  - Update pin color in shape viewer
  - Add comparison gate and global wire transmitter additional data support in blueprints
  - Update item, fluid, and signal producers additional data in blueprints
    - Add function in shape code generator to determine if a shape is fully empty
  - Remove 'k' color code :
    - Update global infos shape colors constant
    - Update readme
    - Update /msg all-colors
  - Update label default text in blueprints
  - Update /msg pins
- Type annotation tweaks
- Add hack to not require global infos module in shape viewer
- No longer try to convert to int value of /size display parameter in the string length is more than the max size int's string len
- Fix shape code generator classifying a shape code as valid when it should not in some conditions

## 25 Apr 24
- Add /msg pins
- Reformat `messages.json`
- Make reduced removed island size constant dependent of default removed island size constant in islands module of game infos
- Separate platform unit count into platform unit cost and platform tile count and add building tile count to /blueprint-info
- Fix full paint operation image not being removed
- Fix mirrored train station islands not being included in islands of game infos

## 12 Apr 24
- Update for alpha 19 :
  - Add version in game infos
  - Update buildings and islands in game infos
    - Change island ordering in json file from size to ingame toolbar placement
  - Add colorblind pattern functionality to shape viewer :
    - Add /cb display parameter
    - Add 'colorblind' parameter to /operation-graph
  - Change purple to magenta :
    - Update shape colors constant in global infos
    - Remove `m` -> `p` shape code character replacement
    - Update /msg all-colors
    - Update readme
    - Update color characters in shape viewer
    - Update shapes in game infos research
  - Remove train station building additional data support in blueprints
  - Support for space pipe additional data in blueprints
  - Remove shape and fluid crates in blueprints additional data and in /blueprint-creator
  - Remove full paint operation in /operation-graph
  - Update uncolored color in shape viewer
    - Update /msg all-shapes
- Use external file for buildings to replace in extract game infos script
- Fix /operation-graph having no description for the 'spoiler' parameter
- Fix operation graph doc not including mention of 'spoiler' parameter at the start
- Fix 'whether' being spelled 'wether' in operation graph doc and command descriptions

## 10 Apr 24
- Add `exitCommandWithoutResponse()` function to owner only commands if executed without owner permission
- Use font files instead of system fonts
- Add Docker things
- Add /msg patreon and sharebp
- Antispam small tweaks :
  - Use global infos constant for time interval between messages
  - Use `dict.pop(key)` instead of `del dict[key]`
  - Ignore exception for if failure to delete a message due to it already having been deleted
- Fix not having a check for if the decoded value is a json object in blueprint decoding

## 22 Mar 24
- Update for alpha 18 :
  - Add version in game infos
  - Update buildings and islands in game infos
  - Support for white train color in blueprints
  - Remove json whitespace in blueprint encoding
- No longer rectify blueprint center on blueprint encoding

## 20 Mar 24
- Update shape viewer response text formatting
- Make private non shape operation functions from shape operations module
- Make private `preRenderAllNames()` function from research viewer module
- Change button additional data decoding to be like ingame
- Remove try excepts to let blueprint encoding exceptions propagate up
- Add error logging to `on_message` event
- Add 'spoiler' parameter to /operation-graph
- Fix not having removed /operation-graph unstack operation
- Fix readme wording
- Fix display parameters and shape codes in shape viewer being accepted where they shouldn't

## 14 Mar 24
- Use 'discord.utils' constants and methods instead of custom ones
- Change train station additional data decoding in blueprints to treat the number as a little endian int16 which is more likely what's used by the game
- Fix not having updated to support buttons additional data in blueprints

## 13 Mar 24
- Tweaks to shape viewer :
  - Reduce windmill side border length to avoid extra border pixels
  - Add comments to say what each draw function draws
  - Fix some inconsistent formatting
  - Fix some windmill dimensions being based on quad size with border instead of without
- Tweaks to bot module formatting
- Capitalize command descriptions that start with a badge
- Add bool value to `registerAdminCommand()`
  - Make /restrict-to-roles-set-inverted use it
  - Convert /pause and /unpause to /set-paused and use it
- Add /set-antispam-enabled to have antispam be enabled or not per server
  - Modify antispam to keep track of messages per server and not globally
- Add /set-antispam-alert-channel to allow having a channel where alerts are sent when the antispam is triggered
- Fix guild settings not setting a default value to a setting if the guild already has other settings set
<br><br>
- Fix readme formatting
- Fix usage cooldown not being per server

## 08 Mar 24
- Update for alpha 17 :
  - Add version in game infos
  - Update buildings and islands in game infos
  - Update shape viewer :
    - Update windmill and crystal look
    - Update black and shape border color
    - Update /msg all-shapes
- Rewrite shape viewer code
- Fix island metadata for tunnel entrance and exit containing unnecessary 0 width/height rectangles in their build area override

## 05 Mar 24
- Add usage cooldown functionality
  - Move code to get the current time into its own function
- Add back required nonlocal declaration in /blueprint-creator
- Add more descriptive error message when executing /blueprint-creator with 'to_create' set to one of the 'item-producer-with' but without the 'extra' parameter set
- Fix not all internal instances of term 'server' being replaced with 'guild'

## 04 Mar 24
- Add automatic messages support
- Add debug menu auto message
- Port antispam feature from sbe
- Add all-shapes and all-colors /msg messages
- Add /access-blueprint command
  - Move blueprint info generation code to its own function
  - Move message content and attachments concatenation code to its own function
- Use global infos constants for 'blueprint' and 'blueprint_file' slash command parameter's description
- Rename 'image file too big' to 'file too big'
- Reorder shape names in readme
- Tweak layer size reduction value in shape viewer
- Fix /blueprint-creator not checking for permission to execute the command
- Fix /blueprint-info having no description for the 'advanced' parameter

## 03 Mar 24
- Update for alphas : 15.2-wiretest1, 16-researchtest1, 16, 16.1 :
  - Add regular or modified version names in game infos
  - Update buildings in game infos
  - Update islands in game infos
    - Update island size
    - Add support for build area overrides
  - Add note in readme for /research-viewer not being updated
  - Add support for island additional data in blueprints module
  - Update blueprints module for train stations, space belts and rails additional data
  - Update pin pusher in shape operations module
  - Fix latest public game version not being updated for the demo
- Remove duplicate blueprint code inputting instructions in readme
- Use island names instead of IDs in island counts of /blueprint-info with advanced=true
- Include `extractGameInfos.py` script in repo
- Update operation graph doc wording
- Add 'advanced' parameter to /change-blueprint-version
- Remove leading and trailing whitespace in slash commands blueprint inputs
- Remove unneeded `nonlocal` declarations in slash commands
- Fix paint and full paint operations in /operation-graph not keeping the color of unpaintable shapes
- Fix crystals not being connected vertically in shape operations module

## 15 Feb 24
- Update for alpha 15.3 demo pins : add modified version name in game infos
- Make blueprints module blueprint objects' encode functions private
- Update shape viewer response formatting
  - Fix `:` in links not being escaped
- Implement cache for /research-viewer with level=0 and node=0
- Add level number above levels in research viewer
- Separate milestone from sidegoals in research viewer
- Change shape viewer layer size reduction amount
- Change bot name to 'Fake ShapeBot 2'
- Change `utils.sepInGroupsNumber()` function code to use builtin f-string formatter
- Fix /operation-graph pin pushing operation not making unsupported quadrants fall
- Fix decoding blueprints with item producers producing fluid crates causing an error
- Fix type of an island or building entry's rotation being `int` instead of `utils.Rotation` when decoding blueprints
- Fix blueprint encoding using 4 spaces as indent in the JSON while the game uses 2

## 11 Jan 24
- Update for alpha 15.3 demo : add version in game infos

## 08 Jan 24
- Update for alpha 15.2 demo : add version in game infos
- Add changelog link to readme
- Rename user displayed term 'island' to 'platform'
- Add platform unit count and blueprint cost to /blueprint-info
- Change /blueprint-info response format
- Add exception name to most error messages triggered by an `except Exception`

## 06 Jan 24
- In blueprints module, move tile dict representation creation from decoding part to building or island blueprint object creation
- Use set instead of dict for overlapping tiles check in blueprint decoding
- In blueprints module, move building blueprint creation from island blueprint from decoding part to blueprint object creation
- Remove some repeated code for building/island blueprint decoding in `decodeBlueprint()` function
- Use different coding approach for at least a bit complex slash commands reducing indentation levels and `else:` count
- Rename `toJSON()` blueprint encoding functions to `encode()`
- On blueprint encoding error, precise in which of the two parts the error happened
- Add /blueprint-creator command
  - Add latest major version constant to version module of game infos
  - Separate latest public and latest patreon-only game versions into two constants
  - When a blueprint building entry that should have additional data is created without any, it will now get its default
- Fix blueprints module producing error when decoding blueprints containing train stations older than alpha 15.2
- Fix `bot.globalLogMessage()` not acting correctly if the message is more than 2000 characters
- Fix /change-blueprint-version command returning error messages in code blocks (again)
- Fix not accounting for fluid producers actually saving their color with the `color-` prefix in blueprints
- Fix constant signal generated fluid value not being represented like a fluid producer's generated fluid
- Fix blueprint encoding not omitting keys

## 04 Jan 24
- Add shapez 1 discord server invite /msg message
- Update readme formatting
- Update game infos islands version to alpha 15.2
- Use prettier syntax to import game infos modules
- Blueprint encoding now omits keys when possible
- In blueprint decoding error messages, when a Pos is mentioned, specify if it's raw or rectified
- `safenString()` in public /msg command
- Move some repeated code for getting blueprint code from string or file in slash commands into a function
- Move repeated code for getting a command response into a function
  - Remove now unused `utils.handleMsgTooLong()` function
- Remove unused variable in `utils.decodedFormatToDiscordFormat()`
- Add support for decoding building additional data in blueprints
  - Add decode and encode string with length functions to utils module
  - Add `isShapeCodeValid()` function to shape code generator module
    - Move the checks for if the shape code is valid from the `generateShapeCodes()` function into their own functions

## 21 Dec 23
- Update for alpha 15.2 : add version, update buildings and research in game infos
- Use code block for in-discord logged error messages
- Implement unknown error handling working for every command
- Potentially fix unknown error when having a loop in the nodes of a /operation-graph graph
- Fix /change-blueprint-version command returning error messages in code blocks

## 17 Dec 23
- Add /msg command with disambiguation screenshot message
- Overhaul server settings system :
  - Rename general term 'server settings' to 'guild settings' to better match discord's internal naming
  - Move guild settings handling to its own module
  - Fix not having a check in role list admin commands to verify that a role has been passed when using the 'add' or 'remove' subcommands
- Use (prettier) builtin methods in blueprint decoding code
- Move some code out of the `on_ready()` event
- Add note in readme for slash commands response type
- Make game infos load functions private
- Fix readme saying the bot will only react with alpha versions of blueprints (post-alpha versions support is planned)

## 16 Dec 23
- Update for alpha 15.1 demo : add version in game infos
- Regroup the `discord.utils.escape_mentions()` used in public shape viewer, /operation-graph and /research-viewer into a `safenString()` function

## 12 Dec 23
- Update for alpha 15 demo : add version in game infos

## 11 Dec 23
- Reintroduce changelog to better see progress on this project
- Update for alphas : 12 demo, 13 demo, 13.5 demo, 13.6 demo, 13.7 demo, 14 demo, 14.1 demo, 14.2 demo, 14.3 demo : add versions in game infos
- Added filtered game infos for extra features and easier updating between game versions
- Big overhaul to the blueprints module, only user visible changes should be:
  - Better error messages
  - Accurate blueprint size
  - Both building scale and island scale size in island blueprints
- Separated building counts in categories and subcategories in /blueprint-info with advanced=true
- Added research viewer
- Added util function to add thousands separators in numbers, used in /research-viewer goal shape amount and /blueprint-info building/island counts
- Allow for other characters than "0" or "1" when using the +struct parameter in shape viewer to account for the differing behavior of pins and crystals
- Fixed uncolored not being listed in readme
- Fixed error when viewing shape codes that all resulted in empty shapes
- General code refactoring : lots of things moved around but hopefully still functions the same