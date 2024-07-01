# Fake ShapeBot 2

## Shape viewer

Put your shape code and parameters in `{}`

### Shapes

- Colorable :
  - C : Circle
  - R : Square/Rectangle
  - S : Star/Spike
  - W : Diamond
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

### Parameters

Each parameter must have a `+` in front of it

- +struct : Use `0` and `1` in your shape code and they will be replaced by nothing or a circle with the color depending on the layer
- +fill : For each layer, if it contains one quadrant, that quadrant will be repeated 4 times, if two quadrants, they will be repeated 2 times
- +lfill : Same as `fill` but with layers instead of quadrants
- +cut : Will cut the shape in half and show the two resulting shapes
- +qcut : Same as `cut` but will cut the shape in 4 instead of 2
- +lsep : Will separate each layer of the shape

Note : `cut` and `qcut` are mutually exclusive

### Additional features

- If the shape code starts with either `level`, `lvl` or `m` followed by a number, it will produce the shape for the corresponding milestone
- Shape expansion : Colorable shapes (like `C`) not followed by a color will have `u` appended (`Cu`), uncolorable shapes (like `P` or `-`) not followed by `-` will have `-` appended (`P-` or `--`)

No matter in which order you put your parameters in your shape code, they will be executed in the following order :\
milestone shapes, lfill, struct, shape expansion, fill, lsep, cut/qcut

### Display parameters

Display parameters must be put outside of the `{}`, have a `/` in front of them and have a `:` separating the parameter name from the value (if there is one)

- /size:80 : Will control the width and height in pixels of each shape (default:56, min:10, max:100)
- /spoiler : Will mark the resulting image as spoiler
- /result : Will additionally send the generated shape codes
- /3d : Will additionally send links to [DontMash's 3D shape viewer](https://shapez.soren.codes/shape)
- /colors : Will control the color skin used for shapes (default:RGB, available:RGB,RYB,CMYK,RGB-cb)

Note : shapes with more than 4 layers and/or with more/less than 4 quadrants per layer are supported

## Slash commands

Note : as a general rule, slash commands will always send private responses except if specified in the command's description or in a parameter

#### Inputting a blueprint code in a command:

If you have the blueprint code as text, paste it in the 'blueprint' parameter. If you have a `txt` or `spz2bp` file, upload it using the 'blueprint_file' parameter. Pro tip : if you have a blueprint code as text that is longer than 6000 characters, click the 'blueprint_file' parameter but instead of clicking the 'upload file' button, paste in the blueprint code text to convert it to a `txt` file. Note : if you provide a file and the 'blueprint' parameter is required, fill it in with dummy characters.

### Public commands

- /view-shapes [message] : Will trigger the shape viewer like a regular message but will send the response back only to you and will also include any error messages

- /change-blueprint-version [blueprint] [version] [blueprint_file=None] [advanced=False] : Changes a blueprint's version and returns the new code. If 'advanced' is set to true, the blueprint will be fully decoded before changing the version (for exemple useful when loading a blueprint from an old version that produces an error ingame because it contains something with an old format)

- /member-count : Displays the member count of the server it is executed in (with additional info such as online/offline count and percentage)

- /operation-graph [instructions] [public=False] [see_shape_vars=False] [spoiler=False] [color_skin=RGB] : See the [/operation-graph documentation](https://github.com/Loupau38/Fake-ShapeBot-2.0/blob/main/operationGraphDoc.md)

- /blueprint-info [blueprint] [advanced=False] [blueprint_file=None] : Will give the version, type, blueprint cost, platform unit cost, building count, building scale size, building tile count, platform count, platform scale size, platform tile count and icons of the given blueprint. If 'advanced' is set to True, will also give the individual counts for every building and platforms

- /research-viewer [level=0] [node=0] [public=False] : Without the 'level' or 'node' parameters set, displays the entire research tree. With the 'level' parameter set to a number starting from 1, displays the corresponding level (milestone + side goals). With the 'level' and 'node' parameter set to a number starting from 1, displays the corresponding node of the corresponding level (1 for the milestone then starting from 2 for the side goals). If 'public' is set to true, the result will be sent publicly in the channel the command was executed in. Error messages will also be sent publicly if this parameter is set to true. When viewing a single node, will display via text the node's name, id, description, goal shape, goal amount, unlocks, lock/unlock commands. Note : the version of the research tree is included in the bottom left of the images created by this command. Important note : the research tree is the one of alpha15.2-wiretest1, updated version comming soon™

- /msg [msg] [public=True] : A command for shortcuts to messages. Enter the message id in the 'msg' parameter. The 'public' parameter will determine if the message will be sent publicly in the channel the command was executed in or not ('True' by default !)

- /blueprint-creator [to_create] [extra=""] : A command for creating blueprints. The created blueprint will depend on the 'to_create' parameter :
  - item-producer-w-shape : Will create a blueprint containing an item producer producing the shape code in the 'extra' parameter. Standard shape code generation can be used, e.g. `C+fill`
  - all-buildings : Will create a blueprint containing all buildings, starting at X=0 and increasing (Y=0 for all, Z is 0 or increased so no building tiles are below 0). Note : this is intended for testing external blueprint related tools, pasting the blueprint ingame will result in errors and not placed buildings
  - all-platforms : Same as above except with platforms instead of buildings

- /access-blueprint [blueprint] [blueprint_file=None] : Access a blueprint. To input a blueprint, use the 'blueprint' or 'blueprint_file' parameters or right click a message and select the 'access-blueprint' app command. The response will include blueprint infos like in /blueprint-info with 'advanced' set to false, a link to view the blueprint in [DontMash's 3D blueprint viewer](https://shapez.soren.codes/blueprint), as well as `txt` and `spz2bp` files containing the blueprint

### Admin commands

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

### Owner commands

- /global-pause : Pauses the bot globally
- /global-unpause : Unpauses the bot globally
- /stop : Stops the bot

## Additional message content related features

- If the bot is mentioned, it should react with `:robot:`
- If one (and only one) blueprint code is detected in a message and its attached files, the bot will react with the version of that blueprint
- If a message contains one attachment and it's a screenshot containing the debug menu, the bot will send a message informing how to close that menu
- Port of sbe's antispam : if a user sends 4 times in a row the same message in the same server at max 10 seconds interval, the bot will time them out for an hour and the messages in question will be deleted

[Changelog](https://github.com/Loupau38/Fake-ShapeBot-2.0/blob/main/changelog.md)