# Operation Graph Documentation

The /operation-graph command allows you to generate a graph of multiple shape transformations in a row (cut, stack, etc).

## Syntax

/operation-graph [instructions]\
Optional parameters : [public] [see_shape_vars] [spoiler] [color_skin]

## Shape variables

In this command, "shape variables" are used to contain shape codes either defined by the user or by the result of an operation. Shape variables are simply a positive integer. A shape variable can't be used as an input multiple times and can't be asigned to/used as an output multiple times. They can also not be used as an input if they haven't be asigned a value (by manual definition or result of an operation). However, if a variable is only used as output and not as input it will automatically be considered a "final output" and put at the bottom of the graph.

## Instructions

The `instructions` parameter is a list of instructions separated by `;`. An instruction is one of the following :

- **Shape definition** : A shape definition is of the syntax `shapeVariables=shapeCode`. The shape code section contains what you would put between `{}` when using the shape viewer. The shape vraiables section contains shape variables separated by `,`. Outputed shape codes are then assigned to the corresponding variables. Therefore, the number of variables given must match the number of shape codes outputed.\
Examples : `1=CuCuCuCu`, `5=R:C+fill`, `3,8=SuSuSuSu+cut`, `1,2,3,4,5,6,7,8=C:C+fill+qcut+lsep`

- **Operation** : An operation is of the syntax `inputShapeVariables:operation:outputShapeVariables`. The in- and output shape variables sections contain shape variables separated by `,`. The operation section is the identifier for the desired operation. The input variables will be passed on to the operation and its outputs will be assigned to the output variables. Therefore, the number of in- and output variables given must match the number of in- and outputs of the operation. Note : some operations take a color in input, the corresponding input must be the color's one letter code.\
Examples : `1:r90cw:2`, `3,7:stack:5`, `10,15:sh:4,21`, `6,r:paint:11`

## Operations

- cut :
  - 1 input
  - 2 outputs : west half, east half
  - Cuts the shape in half
- hcut :
  - 1 input
  - 1 output : east half
  - Destroys the west half of the shape
- r90cw :
  - 1 input
  - 1 output
  - Rotates the shape by one quadrant clockwise
- r90ccw :
  - 1 input
  - 1 output
  - Rotates the shape by one quadrant counterclockwise
- r180 :
  - 1 input
  - 1 output
  - Rotates the shape by 180°
- sh :
  - 2 inputs
  - 2 outputs
  - Swaps the west halves of both shapes
- stack :
  - 2 inputs : bottom shape, top shape
  - 1 output
  - Stacks the top shape on top of the bottom shape
- paint :
  - 2 inputs : shape, color
  - 1 output
  - Paints the top layer of the given shape in the given color
- pin :
  - 1 input
  - 1 output
  - Lifts the shape up one layer and places a pin under every non-empty quadrant of the old bottom layer
- crystal :
  - 2 inputs : shape, color
  - 1 output
  - Replaces empty quadrants and pins with crystals of the given color

## Additional parameters

- `public` (default : false) : When true, the resulting graph will be sent publicly in the channel the command was executed in. Error messages will also be sent publicly if this parameter is set to true.
- `see_shape_vars` (default : false) : For every shape on the graph, the corresponding shape variable number will be displayed and the shape code associated with every shape variable will be sent via text.
- `spoiler` (default : false) : Whether or not to mark the resulting image as spoiler
- `color_skin` (default : RGB) : Which color skin to use to render shapes