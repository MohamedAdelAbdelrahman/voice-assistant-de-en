# Maintenance handbook (EN)

Fictional handbook for the demo plant (lines 1–5, machines 1–12). One section per
alarm code or procedure. `de.md` has the same sections with the same IDs.
"Keywords" lines exist only for search and are not read out.

## [E-204] Spindle temperature too high
Meaning: the spindle of a CNC mill (machines 3 and 4) is above 70 °C. The machine stops the spindle on its own.
Steps: let the spindle cool down for at least 15 minutes. Check the coolant level and the coolant filter. Check that the chip conveyor is not blocked. If the alarm comes back within one hour, the spindle bearing may be worn: create a ticket with priority high.
Safety: do not touch the spindle or the tool while it is hot. Do not open the machine before lockout (see LOTO).
Keywords: spindle, temperature, overheating, hot, coolant, bearing, CNC, mill

## [W-118] Tool wear above 80 %
Meaning: the cutting tool has reached 80 % of its planned life. The machine keeps running, but surface quality goes down.
Steps: plan a tool change at the next part change or at the end of the batch. Use the tool change procedure (see TOOL-CHANGE). Reset the tool life counter on the control panel after the change.
Keywords: tool, wear, worn, cutter, change, life, counter

## [E-512] Shielding gas pressure too low
Meaning: the welding robot gets less than 1.5 bar shielding gas. Weld seams would be porous, so welding is blocked.
Steps: check that the gas cylinder valve is open and the cylinder is not empty (below 10 bar means empty). Change the cylinder if needed. Check the gas hose for kinks and leaks. Then acknowledge the alarm on the robot panel.
Safety: secure gas cylinders with the chain. Only change cylinders with the valve closed.
Keywords: welding, gas, shielding, argon, pressure, cylinder, bottle, leak, robot

## [E-513] Emergency stop triggered
Meaning: an emergency stop button or a safety door switch has been triggered. All movements on the cell are stopped.
Steps: find out why the emergency stop was pressed and make sure nobody is in the danger zone. Remove the cause first. Then pull or turn the emergency stop button to release it, close all safety doors and press reset on the panel. Restart the machine in manual mode first.
Safety: never bridge or bypass a safety door switch. If someone was hurt, call first aid and the shift leader before restarting.
Keywords: emergency stop, e-stop, emergency, stop button, safety door, reset, restart

## [W-301] Waiting for material
Meaning: the machine is ready but has no parts in the infeed. This is not a fault of the machine.
Steps: check the buffer before the machine and the upstream station. Call logistics if the material supply is empty. If the upstream machine is stopped, solve its alarm first.
Keywords: material, waiting, parts, supply, infeed, starved, logistics, buffer

## [I-020] Filter change due
Meaning: the air filter of the drying oven reaches its change interval soon. The oven keeps working.
Steps: plan the filter change in the next planned stop. Filter type F7, two pieces. Let the oven cool below 40 °C before opening it, then reset the filter counter.
Keywords: filter, air filter, oven, dryer, change, interval, due

## [W-150] Hydraulic oil temperature elevated
Meaning: the hydraulic oil of a press is above 55 °C. Above 65 °C the press stops.
Steps: check the oil cooler fan and clean the cooler fins. Check the oil level in the sight glass. Reduce the stroke rate until the temperature drops. If the oil is dark or smells burnt, create a ticket for an oil change.
Safety: hydraulic lines can be under high pressure even when the press is stopped. Release the pressure before opening any line.
Keywords: hydraulic, oil, temperature, press, cooler, hot, pressure

## [I-001] Scheduled maintenance in progress
Meaning: maintenance has the machine in planned maintenance. It must not be started by production.
Steps: ask the maintenance team for the planned end time. Only maintenance removes the lockout and releases the machine.
Keywords: maintenance, scheduled, planned, service, release, locked

## [LOTO] Lockout before opening a machine
Before you open a machine, reach into it or work on it, it must be locked out (lockout/tagout).
Steps: one, stop the machine with the normal stop. Two, switch off the main switch. Three, put your personal padlock on the main switch and hang your tag on it. Four, release stored energy: pressure, springs, hot parts. Five, test that the machine cannot start, using the start button. Only then open the guards. Every person working on the machine uses their own lock.
Keywords: lockout, tagout, LOTO, lock, padlock, open, guard, door, safety, main switch, energy, work on machine, safe

## [PPE] Personal protective equipment
On the whole shop floor: safety shoes and safety glasses. Hearing protection at the presses on line 1. At the welding robots: welding curtain closed, no looking into the arc without a welding shield. For coolant and oil: protective gloves.
Keywords: protective equipment, PPE, shoes, glasses, goggles, hearing protection, gloves, welding shield, safety

## [TOOL-CHANGE] Changing a tool on a CNC mill
Steps: stop the program at the end of a cycle. Move the spindle to the tool change position. Lock out the machine (see LOTO) before reaching into the work area. Wear cut-resistant gloves. Release the tool holder, insert the new tool and check the tool number. Enter the tool length offset in the control, then run the first part in single block mode and check its dimensions.
Keywords: tool change, change tool, cutter, insert, CNC, mill, tool holder, offset

## [ESCALATION] Who to call
Machine fault you cannot solve within 15 minutes: maintenance hotline, extension 2400. Safety issue or injury: shift leader and first aid, extension 112 on the plant phone. Quality problem: quality inspector of the line. Create a ticket for every fault that needs a technician.
Keywords: call, contact, phone, hotline, help, shift leader, first aid, injury, injured, hurt, accident, maintenance team, escalate, who
