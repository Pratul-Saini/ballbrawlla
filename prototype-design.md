Prototype requirements

Character mechanics:
Left, right arrows running movement
Fixed movement speed
Up arrow: jump
Double jump (or as a power up)
Down arrow
While running slide?
Downs character when not moving?
Wall jumping - Stick onto a wall when jumping into it
Opposite direction (left or right arrow) input of wall to jump out
Gradually slide down if no input
Up arrow input jumps/scales wall
Input (left or right arrow) into wall does nothing (or sticks to position)?
Throwing
Fixed position when throwing
Input to activate throw phase (Z)
Deactivate input for testing maybe
Some kind of radial aiming
left/right arrows to choose angle
up/down arrows to choose power
Some input to actually throw (X)

Environment
2d rectangular space with Vertical and horizontal platforms
Floating or connected
Ground and ceiling walls to prevent falling/escaping off map
Left and right walls to prevent running off map
Ball should bounce with the physics against any platform (or environment generally)

Physics
Gravity for ball and player
Doesn’t need to be equal, needs to feel good/fun. Start with equal
Model position, velocity, and acceleration for player and object
Player moves 
translationally at a constant speed
Element of tiredness? Stamina? Maybe not for prototype
Offense has less stamina than defense
Laterally with gravity 
Sliding down wall has friction
Ball moves
Moves parabolically with gravity when not touching environment
Bounces realistically with/without energy loss against platforms
Shape can be spherical or elliptical
For prototype we can assume a model that’s independent of the ball’s scale

