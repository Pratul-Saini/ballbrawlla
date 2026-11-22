Further Gameplay features
Players are designated a team
Offense vs Defense
3 total objects at all times:
Offsense:
Quarterback
Can throw the ball only in any chosen direction in power level. No restrictions in direction or intensity other than radial directionally and power min/max defined from physics config
Wide Receiver
Has all movement mechanics of running, sliding, catching/picking up ball
Cannot throw
Defense
Defender
Has all movement mechanics of running, sliding, catching/picking up ball
Cannot throw
Can tag Wide Receiver with input Z
Environment updates
End zones
Harder platforming
Center field: 100 yards (translate unit into game design)
Primary platforming with intermediate difficulty and variance
Gameplay
2 phases:
Play Call:
Offense chooses where the quarterback will throw (only visible on Offense player’s screen). There is 15 seconds here to choose the angle and power of the throw`
Defense chooses which platform to spawn the Defender at least 10 yards away in the x axis and on the side closer to the Defense’s end zone. The defense can always spawn anywhere in their end zone. These define the spawn’s boundaries along the x axis. The y-axis is fair game. The player must choose a spot on a platform - cannot be floating
Play Execution
Defender spawns in chosen location
Wide Receiver spawns adjacent to the Quarterback
10 seconds of free running for both players before throw is executed
Once ball is thrown, it can be caught by either player
If ball lands, there is 3 seconds to pick up the ball before the play is dead
If the ball is caught/picked up by the Wide Receiver, then the Defender’s goal is to tag the Wide Receiver. Wide Receiver is aiming to reach the Defender’s end zone 
If the ball is caught/picked up by the Defender, the Wide Receiver’s goal is to tag the Defender. Defender’s goal now is to reach the Wide Receiver’s end zone. This is the notion of an interception
Tagging the player with the ball or reaching the opponent’s endzone with the ball ends the Play Execution phase
A play always starts from the last platform the Wide Receiver was tagged at. If the Wide Receiver was tagged mid-air, then the play starts from the last platform the Wide Receiver touched
There are 4 total downs, or 4 Play Calls + Executions, that the Offense can execute before switching sides
The Offense has 4 total downs to reach a platform in the Defense’s end zone. Failure to reach will switch sides
Switch slides results in the play starting from 10 yard line to <some min distance>. Quarterback can spawn anywhere in this region at the beginning but not in their own endzone
The Defense can see where the Offense is picking the Quarterback’s spawn in realtime. The throw angle and power is invisible to the Defense. This lets the Defense reasonably choose a spawn for the Defender
In downs 2-4, the Quarterback spawns exactly where the last play died using the rules defined prior (platform and mid-air wise)
