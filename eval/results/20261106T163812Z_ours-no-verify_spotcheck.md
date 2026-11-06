# Spot check - answer correctness judgments

Seeded sample (seed=42) of 10/32 judged items.
Fill the 'human verdict' line for each; agreement rate goes in the paper.

## test-001 - judge: **incorrect**

- question: Plumber is piping the new tank-type water heater in the mechanical room and the unit has no built-in heat traps. How should the inlet and outlet piping be routed off the heater?
- reference answer: Route piping to and from the water heater horizontally and downward at least 610 mm (24 in) before turning upward, forming a heat trap (22 00 00, 3.2.3).
- drafted answer: Because the water heater does not have integral heat traps, heat traps must be installed directly on both the inlet and outlet piping where vertical pipe risers are used (per UFGS-22-00-00:0204). An acceptable field-built heat trap arrangement is to use elbows so that the inlet and outlet piping make a vertical upward run of not less than 600 mm (24 inches) before turning downward or horizontally into the water heater's inlet and outlet fittings; alternatively, a commercially available heat trap specifically designed to restrict thermosiphoning may be used (UFGS-22-00-00:0204). Note that the specification also separately requires that piping to and from the water heater be routed horizontally and downward a minimum of 610 mm (24 inches) before turning upward (UFGS-22-00-00:0205) — this requirement should be coordinated with the heat trap detail above, as the two paragraphs describe different directional routing (upward vs. downward) and the Engineer of Record should confirm which detail governs for this installation.

In addition, connections of metallic pipe to the water heater must be made with dielectric unions or flanges (dielectric nipples are prohibited unless internally lined and designed to limit current flow) (UFGS-22-00-00:0206). A pre-charged expansion tank must also be installed on the cold water supply between the water heater inlet and the cold water supply shut-off valve (UFGS-22-00-00:0207).

This evidence does not address the specific manufacturer's heat trap piping diagram or drawing detail (which per the spec is intended to be shown on the project drawings) — the Engineer of Record should verify the field routing against the drawing detail and resolve the apparent conflict between the upward (600 mm) and downward (610 mm) routing requirements cited above before the plumber proceeds.
- judge reason: The ground truth requires horizontal-then-downward routing at least 610mm before turning upward, but the drafted answer presents a conflicting 'upward' routing requirement and casts doubt on which governs, failing to give the correct definitive answer.
- human verdict: 

## test-004 - judge: **correct**

- question: We finished chlorinating the domestic water system and the first round of bacteria samples came back clean. Can we turn the system over now, or is there a longer clean-result requirement?
- reference answer: Disinfection must be repeated until bacterial tests show no coliform organisms (zero mean coliform density per 100 mL) for at least 2 full days; the system is not accepted until then (22 00 00, 3.9.5.4).
- drafted answer: No, a single clean sample is not sufficient for acceptance. Per the specification, disinfection must be repeated until bacterial tests show zero mean coliform density per 100 milliliters for at least 2 full days, and the system will not be accepted until these satisfactory bacteriological results have been obtained. Therefore, you need continued clean results spanning at least 2 full days (per the sample testing procedure in 3.9.5.3) before the domestic water system can be turned over.
- judge reason: Matches reference: requires zero coliform density for at least 2 full days before acceptance, same as ground truth.
- human verdict: 

## test-005 - judge: **correct**

- question: The electricians are leaving several empty conduits for future data runs. What kind of pull string do they need to leave in them, and how much extra at the ends?
- reference answer: Install plastic pull wire with at least 890 N (200 lbf) tensile strength in empty conduits and leave at least 915 mm (36 in) of slack at each end (26 20 00, 3.1.5.1).
- drafted answer: Per Section 26 20 00, the electricians must install a pull wire in each empty conduit. The pull wire must be plastic with a minimum tensile strength of 890 N (200 pounds), and a minimum of 915 mm (36 inches) of slack must be left at each end of the pull wire.
- judge reason: Matches all key values: plastic pull wire with 890 N (200 lbf) tensile strength and 915 mm (36 in) slack at each end.
- human verdict: 

## test-008 - judge: **correct**

- question: The fixture supplier is offering their standard one-year warranty on the LED troffers. What warranty term does the project actually require for the luminaires?
- reference answer: Provide a written minimum five-year replacement warranty covering material, luminaire finish and workmanship, transferred to the Government (26 51 00, 1.6.1).
- drafted answer: The one-year warranty offered by the fixture supplier does not meet the project requirement. For LED luminaires, the specification requires a written five-year minimum replacement warranty covering material, luminaire finish, and workmanship, transferred to the Government from the original LED luminaire manufacturer. This five-year material warranty must specifically include coverage for all LED drivers and integral control equipment, and replacement when more than 15 percent of LED sources in any lightbar or subassembly are defective, non-starting, or operating below 70 percent of specified lumen output. The finish warranty must cover failure and substantial deterioration such as blistering, cracking, peeling, chalking, or fading. Note that if lighting controls are integrated with the luminaires, a separate five-year minimum warranty also applies to those components. The supplier's standard one-year warranty should be rejected, and a five-year minimum warranty document meeting these requirements should be submitted instead.
- judge reason: Correctly states the five-year minimum replacement warranty covering material, finish, and workmanship, transferred to the Government, matching the reference and spec clause.
- human verdict: 

## test-009 - judge: **correct**

- question: The distributor has a pallet of downlights that have been sitting in their warehouse for about ten months. Can we still use them on this project?
- reference answer: No, unless specified otherwise. Products may not have been manufactured more than six months before delivery to site (26 51 00, 1.5.12.2).
- drafted answer: No. Per Section 26 51 00, products cannot be manufactured more than six months prior to the date of delivery to the site unless specified otherwise. Since the downlights have reportedly been sitting in the distributor's warehouse for approximately ten months (which exceeds this six-month limit, measured from manufacture to delivery), they would not meet this requirement and cannot be used on this project unless the manufacturing date of the luminaires is verified to be within six months of delivery to the site (the ten months referenced may be warehouse storage time, not necessarily manufacturing date — this should be confirmed with supporting documentation). Note that a related six-month 'satisfactory commercial use' standard also applies under the Standard Products requirement, which concerns product market history rather than storage duration.
- judge reason: Drafted answer correctly states the six-month manufacturing-to-delivery rule from 26 51 00 1.5.12.2 and concludes the downlights cannot be used unless manufacturing date is verified, matching the reference answer's substance despite extra caveats.
- human verdict: 

## test-022 - judge: **correct**

- question: To speed things up above the corridor ceiling, can the electricians strap the EMT runs to the joists and hangers with heavy-duty plastic zip ties?
- reference answer: No. Plastic cable ties are not acceptable for conduit support; use pipe straps, wall brackets, threaded-rod hangers or ceiling trapeze (26 20 00, 3.1.6.12).
- drafted answer: No. The specification explicitly prohibits this method. Section 26 20 00 states that conduit must be supported by pipe straps, wall brackets, threaded rod conduit hangers, or ceiling trapeze, and specifically states that 'Plastic cable ties are not acceptable.' In addition, in suspended-ceiling construction the conduit must be run above the ceiling and must not be supported by the ceiling support system or by joist/hanger tie wires shared with the ceiling grid; conduit and box systems must be supported independently of both the tie wires supporting the ceiling grid system and the ceiling grid system itself. Therefore, zip-tying EMT to joists and ceiling hangers is not an acceptable substitution for the specified support methods, and the electricians must use one of the approved fastening methods (pipe straps, wall brackets, threaded rod hangers, trapeze, etc.) installed independently of the ceiling support system.
- judge reason: Matches reference: prohibits plastic zip ties and specifies acceptable support methods per 26 20 00 3.1.6.12, with accurate added detail.
- human verdict: 

## test-024 - judge: **correct**

- question: For the copper-to-steel connections at the water heater, can we use standard dielectric nipples instead of dielectric unions?
- reference answer: No. Connections of metallic pipe to water heaters must use dielectric unions or flanges; dielectric nipples are prohibited unless internally lined and specifically designed to limit current flow between dissimilar metals (22 00 00, 3.2.4).
- drafted answer: No. The specification directly addresses this condition: connections of metallic pipe to water heaters must be made with dielectric unions or flanges, and the use of dielectric nipples is specifically prohibited unless the nipple is internally lined and specifically designed to limit current flow between dissimilar metals. Standard dielectric nipples (i.e., ones that are not internally lined and specifically designed to limit current flow between dissimilar metals) do not meet this requirement and cannot be substituted. This is further supported by the general requirement for connections between ferrous and non-ferrous (copper) water pipe, which must be made with dielectric unions or flange waterways that are internally lined with an insulator specifically designed to prevent current flow between dissimilar metals.
- judge reason: Matches reference: prohibits standard dielectric nipples unless internally lined and designed to limit current flow, requiring dielectric unions/flanges instead.
- human verdict: 

## test-036 - judge: **correct**

- question: For the blast-cleaned structural steel, our coating sub is following the February 2021 09 90 00, 3.5.2.2, which only names the SSPC blast standards. Is there any requirement now on the surface profile?
- reference answer: Yes. The current (August 2026) 3.5.2.2 adds that the anchor profile recommended by the coating manufacturer must be achieved using the appropriate abrasive. The February 2021 text is superseded.
- drafted answer: Yes. The current version of 09 90 00, 3.5.2.2 (Abrasive Blast Cleaned Surfaces) has been updated from the February 2021 edition your coating sub is referencing. In addition to complying with the applicable SSPC blast standards (SSPC SP 7/NACE No.4, SSPC SP 6/NACE No.3, or SSPC SP 10/NACE No. 2) and using SSPC VIS 1 photographs as a visual reference, the current text now explicitly requires achieving an anchor profile: 'Achieve the anchor profile recommended by the manufacturer using the appropriate abrasive.' Note that the February 2021 revision of 3.5.2.2 (along with 3.5, 3.5.1, and 3.5.2) has been superseded by the UFGS-2026-08 revision, which is the source of this added surface profile requirement.
- judge reason: Matches reference: confirms new anchor profile requirement added to superseding spec, consistent with governing clause text.
- human verdict: 

## test-038 - judge: **incorrect**

- question: Our paint submittal followed paragraph 2.1 of the February 2021 09 90 00 and included only product data sheets. Is that still sufficient for the coating submittal?
- reference answer: No. The current (August 2026) 2.1 Coating Systems requires Product Data Sheets and the Manufacturer's Application Instructions, including detailed mixing instructions, minimum and maximum application temperature and humidity, pot life, and curing and drying times between coats, plus preprinted cleaning and maintenance instructions. The February 2021 2.1 (titled Materials) is superseded.
- drafted answer: The paragraph you referenced (2.1 of the February 2021 revision of Section 09 90 00) has been superseded; that section is now governed by UFGS-2026-08. Under the current revision, submittal requirements for painting are addressed in Part 1, Paragraph 1.6 SUBMITTALS, which requires that items be submitted 'in accordance with Section 01 33 00 SUBMITTAL PROCEDURES' and classified per the SD-series submittal descriptions (e.g., SD-03 Product Data, SD-01 Preconstruction Submittals, etc.) rather than under the old Part 2, 2.1 numbering. However, the evidence provided does not include the specific current list of coating/paint submittal items (the submittal list text is cut off before the painting-specific entries), so we cannot confirm from the available record whether product data sheets alone satisfy the current submittal requirement.

What the evidence does show is that, separately from the submittal-list question, compliance with the painting specification is tied to the current MPI 'Approved Product List' -- 'The current MPI "Approved Product List," ... will be used to determine compliance with the submittal requirements of this specification' and 'No variation from the MPI Approved Products List is acceptable.' This suggests that simply providing manufacturer product data sheets may not by itself demonstrate compliance; the products shown on the data sheets would also need to correspond to an approved MPI listing.

Because the current (2026-08) submittal item list for painting is not fully included in the evidence provided, we cannot give a definitive yes/no on whether product data sheets alone are sufficient. Recommend resubmitting in accordance with the current Section 09 90 00, Paragraph 1.6 SUBMITTALS requirements and Section 01 33 00, and confirming the submitted products appear on the current MPI Approved Product List, for licensed professional review and final determination.
- judge reason: The drafted answer fails to state the correct requirement (Product Data Sheets plus Manufacturer's Application Instructions with mixing/temperature/humidity/pot life/curing details and cleaning instructions) and instead gives an inconclusive, hedged non-answer focused on MPI lists and unrelated submittal procedures.
- human verdict: 

## test-040 - judge: **correct**

- question: The field rep is asking for paint samples under the field sampling paragraph 1.6.6 of the February 2021 09 90 00. What does the current spec require for sampling, and under which paragraph?
- reference answer: Paragraph 1.6.6 is superseded; sampling is now 1.7.5.1 Sampling Procedure in the August 2026 edition. Provide one-liter (one-quart) samples of each part of the selected paint materials, mixing each container before sampling, taken in the presence of the Contracting Officer and labeled.
- drafted answer: The paragraph the field rep cited (1.6.6 'FIELD SAMPLING' in the February 2021 edition of 09 90 00) has been superseded. In the current edition of Section 09 90 00 (UFGS-2026-08), the sampling requirement is now located in PART 1, paragraph 1.7.5.1, 'Sampling Procedure' (under 1.7.5 'Coating Sampling and Testing'), not 1.6.6.

Under the current paragraph 1.7.5.1, the Contractor must provide one liter (one quart) samples of each part of the selected paint materials, mixing the individual container of each component prior to sampling (noting that lack of mixing can lead to product failure and full batch rejection). Samples must be taken in the presence of the Contracting Officer, and labeled and identified, with labels provided in accordance with the paragraph on delivery and storage.

Additionally, per current paragraph 1.7.5 ('Coating Sampling and Testing'), the Contracting Officer may select up to two delivered products (random or at discretion) for Qualification Testing, with samples of each chosen product taken per the Sampling Procedure paragraph and tested per the Testing Procedure paragraph, at no cost to the Government.

Note: The chunks confirm that 09 90 00 PART 1 > 1.6 > 1.6.6 and 1.6.6.1 (Feb 2021) are superseded by the 2026-08 revision; however, the evidence provided does not include the actual superseded 1.6.6 text for direct side-by-side comparison, so only the current requirement (1.7.5.1) can be confirmed here.
- judge reason: Matches reference: identifies supersession to 1.7.5.1, correctly states one liter/quart samples, mixing requirement, presence of Contracting Officer, and labeling.
- human verdict: 
