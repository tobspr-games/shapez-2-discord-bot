# ShapeBot 2

## Shape viewer

Put your shape code and parameters in `{}`

### Shapes

- Colorable :
  - Quad :
    - C : Circle
    - R : Square/Rectangle
    - S : Star/Spike
    - W : Diamond
    - c : Crystal
  - Hex :
    - H : Hexagon
    - F : Flower
    - G : Gear
    - c : Crystal
- Uncolorable :
  - P : Pin
  - \- : Nothing

### Colors

- u : Uncolored
- r : Red
- g : Green
- b : Blue
- c : Cyan
- m : Magenta
- y : Yellow
- w : White
- \- : Nothing

Note : shapes with more than 4 layers and/or with more/less than 4 quadrants per layer are supported

### Parameters

Each parameter must have a `+` in front of it

- +struct : Each shape part must be inputted as a single character for its type. The part's color will depend on which layer it's in. Additionally, `0` will be replaced by `-` and `1` by `C` or `H`. This means that characters that are both a shape type and a color will always be interpreted as a shape type.
- +fill :
  - If using quad shapes, for each layer : if it contains 1 quadrant -> that quadrant will be repeated 4 times, if 2 quadrants -> they will be repeated 2 times
  - If using hex shapes : 1 quadrant -> repeated 6 times, 2 -> 3, 3 -> 2
- +lfill : Same as `fill` but with layers instead of quadrants
- +cut : Will cut the shape in half and show the two resulting shapes
- +qcut : Same as `cut` but will cut the shape in 4 instead of 2
- +lsep : Will separate each layer of the shape
- +hex : Forces the shapes configuration to be hexagonal shapes, useful if the shape only contains shape parts common to quad and hex

Note : `cut` and `qcut` are mutually exclusive

### Additional features

- Shape expansion : Colorable shapes (like `C`) not followed by a color will have `u` appended (`Cu`), uncolorable shapes (like `P` or `-`) not followed by `-` will have `-` appended (`P-` or `--`). Shape expansion will always be applied if using `+struct`
- Shapes configuration guess : If the `+hex` parameter isn't present, the current shapes configuration (quad/hex) will be guessed based on the shape types given in the shape code

No matter in which order you put your parameters in your shape code, they will be executed in the following order :\
lfill, shapes config guess, struct, shape expansion, fill, lsep, cut/qcut

### Display parameters

Display parameters must be put outside of the `{}`, have a `/` in front of them and have a `:` separating the parameter name from the value (if there is one)

- /size:80 : Will control the width and height in pixels of each shape (default:56, min:10, max:100)
- /spoiler : Will mark the resulting image as spoiler
- /result : Will additionally send the generated shape codes
- /3d : Will additionally send links to [DontMash's 3D shape viewer](https://shapez.soren.codes/shape)
- /colors:RYB : Will control the color mode used for shapes (default:RGB, available:RGB,RYB,CMYK,RGB-cb)

### Rows control

The `[sep]` keyword can be used to control the layout in which shapes appear :

- If the message doesn't contain `[sep]` :
  - If there are 10 or less shapes rendered, they will be put in a single row
  - If there are more than 10 shapes, they will be put on rows of 8 shapes, except for the last one which can contain less
- If there is at least one `[sep]` in the message :
  - Shapes will be put on rows without a max size, each `[sep]` will make the following shapes render on a new row below
  - Empty rows are allowed, except leading and trailing empty rows which will be removed

## Slash commands

Note : as a general rule, slash commands will always send private responses except if specified in the command's description or in a parameter

#### Inputting a blueprint code in a command:

If you have the blueprint code as text, select the 'blueprint' parameter and paste it there. If you have a `.txt` or `.spz2bp` file, upload it using the 'blueprint_file' parameter. Pro tip : if you have a blueprint code as text that is longer than 6000 characters, click the 'blueprint_file' parameter but instead of clicking the 'upload file' button, paste in the blueprint code text to convert it to a `.txt` file.

### Public commands

- /view-shapes [message] : Will trigger the shape viewer like a regular message but will send the response back only to you and will also include any error messages

- /update-blueprint [blueprint=None] [blueprint_file=None] : Updates a blueprint to the latest format. Runs the same migration code as ingame as well as some additional convertions.

- /member-count : Displays the member count of the server it is executed in (with additional info such as online/offline count and percentage)

- /operation-graph [instructions] [public=False] [see_shape_vars=False] [spoiler=False] [color_mode=RGB] [max_shape_layers=4] : See the [/operation-graph documentation](https://github.com/tobspr-games/shapez-2-discord-bot/blob/main/operationGraphDoc.md)

- /blueprint-info [blueprint=None] [blueprint_file=None] [advanced=False] : Will give the version, type, blueprint cost, platform unit cost, building count, building scale size, building tile count, platform count, platform scale size, platform tile count and icons of the given blueprint. If 'advanced' is set to True, will also give the individual counts for every building and platforms

- /research-viewer : Will come back soon™

- /msg [msg] [public=True] : A command for shortcuts to messages. Enter the message id in the 'msg' parameter. The 'public' parameter will determine if the message will be sent publicly in the channel the command was executed in or not ('True' by default !)

- /blueprint-creator [to_create] [extra=""] : A command for creating blueprints. The created blueprint will depend on the 'to_create' parameter :
  - item-producer-w-shape : Will create a blueprint containing an item producer producing the shape code in the 'extra' parameter. Standard shape code generation can be used, e.g. `C+fill`
  - all-buildings : Will create a blueprint containing all buildings, starting at X=0 and increasing (Y=0 for all, Z is 0 or increased so no building tiles are below 0). Note : this is intended for testing external blueprint related tools, pasting the blueprint ingame will result in errors and not placed buildings
  - all-platforms : Same as above except with platforms instead of buildings

- /access-blueprint [blueprint=None] [blueprint_file=None] : Access a blueprint. To input a blueprint, use the 'blueprint' or 'blueprint_file' parameters or right click a message and select the 'access-blueprint' app command. The response will include blueprint infos like in /blueprint-info with 'advanced' set to false, a link to view the blueprint in [DontMash's 3D blueprint viewer](https://shapez.soren.codes/blueprint), as well as `txt` and `spz2bp` files containing the blueprint

- /find-replies [message_id] : Searches in all messages sent up to 24 hours after the message given by 'message_id' for replies to that message.

### Admin commands

Important note : guild settings currently can't be modified so most of the commands below won't have any effect

- Pausing :\
  While paused, the bot will not send any public messages on the server
  - /set-paused [value] : Sets if the bot should be paused

- Restrict to channel :\
  The bot will only send public messages on the channel it is restricted to
  - /restrict-to-channel [channel] : Sets the channel to restrict the bot to, don't include the 'channel' parameter to clear it and not restrict the bot to any channel

- Usage cooldown :\
  If a user is in cooldown, they will not be able to use the bot's public, private and reaction features
  - /usage-cooldown [cooldown] : Sets the usage cooldown in seconds

- Antispam :\
  See [below](#additional-message-content-related-features)
  - /set-antispam-enabled [value] : Sets if the antispam feature should be enabled on this server
  - /set-antispam-alert-channel [channel] : Sets the channel where an alert should be sent when the antispam is triggered, don't include the 'channel' parameter to clear it and not have an alert channel

- Restrict to roles :\
  If 'restrictToRolesInverted' is false, only users who have at least one role part of the 'restrictToRoles' list will be able to make the bot send public messages. If true, only users who have at least one role that isn't part of the list will be able to. In both cases, if the list is empty, every user will be able to.
  - /restrict-to-roles [operation] [role=None] : Modifys the 'restrictToRoles' list depending on the 'operation' parameter value :
    - add : Adds a role to the list
    - remove : Removes a role from the list
    - view : View the list
    - clear : Clears the list
  - /restrict-to-roles-set-inverted [value] : Sets the 'restrictToRolesInverted' parameter

- Admin roles :\
  Only users who have a role part of the 'adminRoles' list or who have the administrator permission will be able to use admin commands
  - /admin-roles : Modifys the 'adminRoles' list depending on the 'operation' parameter value :
    - add : Adds a role to the list
    - remove : Removes a role from the list
    - view : View the list
    - clear : Clears the list

- Pins management :\
  Add or move pins in the pinned messages list. Since when pinning messages they can only appear at the top of the list, this is done by first unpinning all messages above the wanted position, pinning the given message, then pinning back the previously removed messages. Positions given in these commands are 1-indexed and start from the top of the pins list.
  - /pin-msg [message_id] [position] : Pins the message given by the ID to the position given. The position given will be the position of the given message once the operation is done.
  - /move-pinned-msg [from_position] [to_position] : Moves a pinned message in the pins list. The 'to_position' will be the position of the moved message once the operation is done. The messages in between 'from' (excluded) and 'to' (included) are shifted by 1 position either up or down, i.e. this operation doesn't swap 'from' and 'to', except if they are next to each other.

- Sus users :\
  Sus users are users which don't have a join message despite being in the server (currently an experiment)
  - /sus-users : Display a list of all sus users

### Owner commands

- /global-pause : Pauses the bot globally
- /global-unpause : Unpauses the bot globally
- /stop : Stops the bot

## Additional message content related features

- If the bot is mentioned, it should react with its logo as an emoji (equivalent of a /ping)
- If one (and only one) blueprint code is detected in a message and its attached files, the bot will send a message containing part of the /access-blueprint command response if the message is in a blueprints channel or one of its threads, otherwise it will react with the version of that blueprint
- If a message contains one attachment and it's a screenshot containing the debug menu, the bot will send a message informing how to close that menu
- If a message contains the hard milestone 8 first shape code, the bot will send a message informing how to create standalone pins
- Modified version of sbe's antispam : if a user sends multiple times in a row the same message(s) in different channels in the same server at max 30 seconds interval, the bot will time them out for an hour and the messages in question will be deleted

[Changelog](https://github.com/tobspr-games/shapez-2-discord-bot/blob/main/changelog.md)