# Spot check - answer correctness judgments

Seeded sample (seed=42) of 10/31 judged items.
Fill the 'human verdict' line for each; agreement rate goes in the paper.

## test-001 - judge: **correct**

- question: Plumber is piping the new tank-type water heater in the mechanical room and the unit has no built-in heat traps. How should the inlet and outlet piping be routed off the heater?
- reference answer: Route piping to and from the water heater horizontally and downward at least 610 mm (24 in) before turning upward, forming a heat trap (22 00 00, 3.2.3).
- drafted answer: Because this tank-type heater has no integral heat traps, heat traps must be installed directly on both the inlet and outlet piping. Per Section 22 00 00, 3.2.2, this applies to "Storage water heaters that are not equipped with integral heat traps and having vertical pipe risers"; an acceptable heat trap configuration is "a piping arrangement such as elbows connected so that the inlet and outlet piping make vertically upward runs of not less than 600 mm 24 inches just before turning downward or directly horizontal into the water heater's inlet and outlet fittings."

In addition, per 3.2.3 (Heat Traps), the piping to and from the water heater must be routed with the following general rule: "Piping to and from each water heater and hot water storage tank must be routed horizontally and downward a minimum of 610 mm 24 inches before turning in an upward direction."

Together, these requirements mean the inlet and outlet connections at the heater must incorporate the elbow/vertical-rise heat-trap arrangement described in 3.2.2, and the overall piping runs to/from the unit must route horizontally and downward at least 610 mm (24 in) before turning upward as required by 3.2.3. The RFI should also note two related piping requirements that affect this installation: connections of metallic pipe to the water heater must be made with dielectric unions or flanges (dielectric nipples are prohibited unless internally lined and specifically designed to limit current flow) (3.2.4), and a pre-charged expansion tank must be installed on the cold water supply between the water heater inlet and the cold water supply shut-off valve (3.2.5).
- judge reason: The drafted answer includes the key 3.2.3 requirement (route horizontally and downward min 610 mm/24 in before turning upward) matching the reference, with additional context that doesn't contradict it.
- human verdict: 

## test-004 - judge: **correct**

- question: We finished chlorinating the domestic water system and the first round of bacteria samples came back clean. Can we turn the system over now, or is there a longer clean-result requirement?
- reference answer: Disinfection must be repeated until bacterial tests show no coliform organisms (zero mean coliform density per 100 mL) for at least 2 full days; the system is not accepted until then (22 00 00, 3.9.5.4).
- drafted answer: No — a single clean bacteria sample is not sufficient for turnover. Per the specification, disinfection must be repeated until bacterial tests show zero mean coliform density per 100 milliliters for at least 2 full days, and the system will not be accepted until satisfactory bacteriological results have been obtained over that period. You will need to continue sampling to confirm clean results are sustained for the full 2-day duration before the domestic water system can be turned over.
- judge reason: Matches reference: requires zero coliform results sustained for at least 2 full days before acceptance.
- human verdict: 

## test-005 - judge: **correct**

- question: The electricians are leaving several empty conduits for future data runs. What kind of pull string do they need to leave in them, and how much extra at the ends?
- reference answer: Install plastic pull wire with at least 890 N (200 lbf) tensile strength in empty conduits and leave at least 915 mm (36 in) of slack at each end (26 20 00, 3.1.5.1).
- drafted answer: Per the specification, pull wires installed in empty conduits must be plastic with a minimum tensile strength of 890 N (200 lbs). At each end of the pull wire, a minimum of 915 mm (36 inches) of slack must be left.
- judge reason: Matches reference: plastic pull wire with 890 N (200 lbf) tensile strength and 915 mm (36 in) slack at each end.
- human verdict: 

## test-008 - judge: **correct**

- question: The fixture supplier is offering their standard one-year warranty on the LED troffers. What warranty term does the project actually require for the luminaires?
- reference answer: Provide a written minimum five-year replacement warranty covering material, luminaire finish and workmanship, transferred to the Government (26 51 00, 1.6.1).
- drafted answer: The project specification does not accept the supplier's standard one-year warranty for the LED troffers. Per the luminaire warranty requirements, the Contractor must provide and transfer to the Government a written warranty with a minimum term of five years covering material, luminaire finish, and workmanship, including LED drivers and integral control equipment. The one-year warranty offered by the supplier does not meet this minimum requirement.
- judge reason: States the required minimum five-year written replacement warranty covering material, finish, and workmanship, transferred to the Government, matching the reference.
- human verdict: 

## test-009 - judge: **correct**

- question: The distributor has a pallet of downlights that have been sitting in their warehouse for about ten months. Can we still use them on this project?
- reference answer: No, unless specified otherwise. Products may not have been manufactured more than six months before delivery to site (26 51 00, 1.5.12.2).
- drafted answer: No. Per Section 26 51 00, products manufactured more than six months prior to the date of delivery to the site are not permitted, unless the specification indicates otherwise. Since the downlights have been sitting in the distributor's warehouse for approximately ten months, they would have been manufactured more than six months before delivery and therefore do not meet this requirement. These luminaires cannot be used on this project unless the manufacturing date can be documented to be within six months of delivery, or a deviation is otherwise specified.
- judge reason: Matches ground truth: six-month manufacturing rule from 26 51 00 1.5.12.2, concluding downlights cannot be used unless otherwise specified.
- human verdict: 

## test-021 - judge: **correct**

- question: Running a smoke test on the drain and vent system is going to set off alarms in the occupied wing next door. Can we do a peppermint test instead?
- reference answer: Yes, the Contractor may perform a peppermint test in lieu of the smoke test, but must submit a testing procedure and the reasons for choosing it to the Contracting Officer (22 00 00, 3.9.1).
- drafted answer: Yes, a peppermint test is permitted as an alternative to the smoke test for the drainage and vent system final test. The specification states that the Contractor has the option to perform a peppermint test in lieu of the smoke test. However, this option requires prior approval: if a peppermint test is chosen, the Contractor must submit a testing procedure and the reasons for choosing this option in lieu of the smoke test to the Contracting Officer for approval before proceeding. Therefore, you may substitute the peppermint test, but you must first submit the testing procedure and justification to the Contracting Officer and receive approval prior to performing the test.
- judge reason: Matches reference: peppermint test allowed in lieu of smoke test, contingent on submitting procedure and reasons to Contracting Officer for approval.
- human verdict: 

## test-022 - judge: **correct**

- question: To speed things up above the corridor ceiling, can the electricians strap the EMT runs to the joists and hangers with heavy-duty plastic zip ties?
- reference answer: No. Plastic cable ties are not acceptable for conduit support; use pipe straps, wall brackets, threaded-rod hangers or ceiling trapeze (26 20 00, 3.1.6.12).
- drafted answer: No. The specification explicitly prohibits this method: the spec states plainly that 'Plastic cable ties are not acceptable.' Additionally, in suspended-ceiling construction the conduit must be run above the ceiling and supported independently of the ceiling grid/support system and its tie wires — conduit cannot be strapped to the ceiling grid or its hangers, and electrical raceways cannot share supporting means with mechanical piping or ducts.
- judge reason: Correctly states plastic cable ties are prohibited and references appropriate independent support requirements, matching the reference and spec clause.
- human verdict: 

## test-024 - judge: **correct**

- question: For the copper-to-steel connections at the water heater, can we use standard dielectric nipples instead of dielectric unions?
- reference answer: No. Connections of metallic pipe to water heaters must use dielectric unions or flanges; dielectric nipples are prohibited unless internally lined and specifically designed to limit current flow between dissimilar metals (22 00 00, 3.2.4).
- drafted answer: No, standard dielectric nipples are not an acceptable substitute. The specification explicitly requires that connections of metallic pipe to water heaters be made with dielectric unions or flanges, and prohibits dielectric nipples unless they are internally lined and specifically designed to limit current flow between dissimilar metals. This same lining/design requirement applies generally to dielectric connections between ferrous and non-ferrous (copper) piping, which must be internally lined with an insulator specifically designed to prevent current flow between dissimilar metals. Therefore, a standard (non-lined, non-specifically-designed) dielectric nipple would not meet the requirement — only a dielectric union/flange, or a dielectric nipple meeting the internal lining and current-limiting design criteria, is permitted.
- judge reason: Matches reference: dielectric unions/flanges required, standard nipples prohibited unless internally lined and designed to limit current flow.
- human verdict: 

## test-034 - judge: **correct**

- question: Mechanical wants to confirm stencil sizes for pipe labeling. Their submittal cites paragraph 3.12 Piping Identification of the February 2021 09 90 00. What letter heights are required under the current edition?
- reference answer: Letters must be at least 13 mm (1/2 in) high on piping and at least 50 mm (2 in) high elsewhere, with arrow markings for flow direction. The 2021 citation is superseded; in the August 2026 edition piping identification is paragraph 3.9 (3.12 is now Paint Tables).
- drafted answer: The paragraph cited by Mechanical (3.12 Piping Identification, February 2021 edition of 09 90 00) has been renumbered in the current edition (UFGS-2026-08) to paragraph 3.9, Piping Identification. Under the current edition, stenciled letters for piping identification must be a minimum of 13 mm (1/2 inch) high for piping and a minimum of 50 mm (2 inches) high elsewhere.
- judge reason: Matches required letter heights (13mm/1/2in on piping, 50mm/2in elsewhere) and correctly notes renumbering to 3.9 in 2026 edition.
- human verdict: 

## test-039 - judge: **correct**

- question: The painter's material list references the interior gypsum board paint table in 3.15.2.5 of the February 2021 09 90 00. Where is that table in the current spec?
- reference answer: Paragraph 3.15 no longer exists. In the August 2026 edition the paint tables are in 3.12, and the interior plaster, gypsum board and textured surfaces table (MPI Division 9) is 3.12.2.5.
- drafted answer: The February 2021 edition's 09 90 00 Section 3.15.2.5 (Interior Gypsum Board/Plaster paint table) has been renumbered in the current UFGS-2026-08 revision. That paint table now appears at PART 3, Section 3.12.2.5, titled "MPI Division 9: Interior Plaster, Gypsum Board, Textured Surfaces Paint Table." The painter should reference this current location (3.12.2.5) rather than the superseded 3.15.2.5 citation from the 2021 edition.
- judge reason: Correctly identifies new location as 3.12.2.5 under 3.12 in current spec, matching reference answer.
- human verdict: 
