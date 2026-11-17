"""Input ranges with their sources, behind containment.inputs_guide.

Typical and plausible ranges in field units for every project input, merged from a
literature review (each source tagged when it is a standard reference not re-checked
online) and from the values used by the 15 Texas Class VI applications rebuilt for
Containment's validation in October 2026 (``seen``). Edit here, not in the form.
"""

RANGES = [{'key': 'iz_top',
  'unit': 'ft',
  'typical': [3000, 10000],
  'plausible': [2000, 16000],
  'seen': '3,500 to 12,200 ft (median 5,900)',
  'gradient': '',
  'if_missing': 'Take the top of the gross injection interval from the type log or structure map '
                'at the well. If only a formation name is given, use the formation top from nearby '
                'RRC well records; confirm it is deeper than about 2,500 ft so CO2 stays '
                'supercritical. CO2 is supercritical above 87.98 F and 1,071 psi. At a 0.433 to '
                '0.465 psi/ft hydrostatic gradient the pressure condition is reached at about '
                '2,300 to 2,500 ft; the temperature condition is reached much shallower (about '
                '1,000 to 1,500 ft on the Gulf Coast). Common screening minimum is about 800 m '
                '(2,625 ft). Gulf Coast Miocene and Frio projects commonly 3,000 to 9,000 ft '
                'Woodbine/Paluxy '
                '(East Texas) about 3,500 to 8,000 ft. Permian San Andres about 3,500 to 6,000 ft; '
                'Devonian and Ellenburger 8,000 to 14,000 ft or more. Below the top of geopressure '
                '(often 8,000 to 12,000 ft on the Texas coast) injectivity margins shrink.',
  'sources': ['IPCC (2005). Special Report on Carbon Dioxide Capture and Storage, Chapter 5 '
              'Underground geological storage. Cambridge University Press. '
              'https://www.ipcc.ch/report/carbon-dioxide-capture-and-storage/ (standard reference, '
              'not re-checked)',
              'RRC CO2 storage notices. '
              'https://rrc.texas.gov/oil-and-gas/applications-and-permits/injection-storage-permits/co2-storage/co2-notices',
              'Span, R. and Wagner, W. (1996). A new equation of state for carbon dioxide... J. '
              'Phys. Chem. Ref. Data 25(6), 1509-1596. https://doi.org/10.1063/1.555991 (standard '
              'reference, not re-checked)']},
 {'key': 'iz_h',
  'unit': 'ft',
  'typical': [50, 600],
  'plausible': [10, 2000],
  'seen': '36 to 2,087 ft (median 380)',
  'gradient': '',
  'if_missing': 'Sum sand (or porous carbonate) footage in the injection interval from the type '
                'log using a shale cutoff (for example Vsh < 0.5) and porosity cutoff (about 10 '
                'percent sand, 5 to 6 percent carbonate). If only gross thickness is given, '
                'multiply by a net-to-gross from the next row. Net-to-gross is typically 0.3 to '
                '0.8 (Wallace et al. 2014). Gulf Coast Miocene/Frio: individual sands 10 to 100 '
                'ft, stacked injection intervals commonly 100 to 1,000 ft gross with 50 to 600 ft '
                'net. Permian San Andres porous dolomite: 50 to 400 ft net.',
  'sources': ['Wallace, K.J., Meckel, T.A., Carr, D.L., Trevino, R.H., Yang, C. (2014). Regional '
              'CO2 sequestration capacity assessment for the coastal and offshore Texas Miocene '
              'interval. Greenhouse Gases: Science and Technology 4(1), 53-65. '
              'https://doi.org/10.1002/ghg.1380',
              'Trevino, R.H. and Meckel, T.A. (eds.) (2017). Geological CO2 Sequestration Atlas of '
              'Miocene Strata, Offshore Texas State Waters. BEG Report of Investigations 283. '
              'https://doi.org/10.23867/RI0283D (standard reference, not re-checked)']},
 {'key': 'iz_phi',
  'unit': 'fraction',
  'typical': [0.15, 0.32],
  'plausible': [0.03, 0.4],
  'seen': '0.04 to 0.33 (median 0.27)',
  'gradient': '',
  'if_missing': 'Use density/neutron log porosity averaged over net intervals, or a regional '
                'porosity-depth trend for Gulf Coast sands. For carbonates, use core or log '
                'averages from nearby San Andres units in the RRC/BEG oil atlases. Gulf Coast '
                'Miocene sands 0.25 to 0.35; Frio 0.20 to 0.35 (Frio pilot about 0.32); Woodbine '
                'and Paluxy 0.20 to 0.30. Permian San Andres dolomite 0.08 to 0.15 (pay average '
                'about 0.10 to 0.12); Devonian Thirtyone chert 0.10 to 0.25; Ellenburger matrix '
                '0.02 to 0.08 (storage relies on karst/fractures). Porosity in Gulf Coast sands '
                'declines with depth (roughly 1 to 1.5 porosity units per 1,000 ft).',
  'sources': ['Hovorka, S.D. et al. (2006). Measuring permanence of CO2 storage in saline '
              'formations: the Frio experiment. Environmental Geosciences 13(2), 105-121. '
              'https://doi.org/10.1306/eg.11210505011 (standard reference, not re-checked)',
              'GCCC/BEG CO2 data pages: Woodbine (https://gccc.beg.utexas.edu/node/576) and Paluxy '
              '(https://gccc.beg.utexas.edu/node/414)',
              'Loucks, R.G., Dodge, M.M., Galloway, W.E. (1984). Regional controls on diagenesis '
              'and reservoir quality in lower Tertiary sandstones along the Texas Gulf Coast. AAPG '
              'Memoir 37, 15-45. (standard reference, not re-checked)',
              'Tyler, N. et al. (1991). Atlas of Major Texas Gas Reservoirs; Galloway, W.E. et al. '
              '(1983). Atlas of Major Texas Oil Reservoirs. BEG. (standard reference, not '
              're-checked)']},
 {'key': 'iz_k',
  'unit': 'mD',
  'typical': [10, 2000],
  'plausible': [0.1, 10000],
  'seen': '1.3 to 3,800 mD (median 800)',
  'gradient': '',
  'if_missing': 'Use core data or well-test (falloff/step-rate) permeability. Lacking these, use a '
                'porosity-permeability transform from analog fields in the same formation; Gulf '
                'Coast clean sands at 25 to 30 percent porosity are usually hundreds of mD. Gulf '
                'Coast Miocene and Frio sands 100 to 3,000 mD (Frio pilot about 2,500 mD); '
                'Woodbine 100 to 1,000+ mD; Paluxy 100 to 1,000 mD. Permian San Andres 1 to 20 mD '
                'typical (0.1 to 100 range); Devonian chert 1 to 50 mD; Ellenburger matrix below 1 '
                'mD, effective 10s to 100s mD where fractured/karsted.',
  'sources': ['Hovorka et al. (2006), Environmental Geosciences 13(2). '
              'https://doi.org/10.1306/eg.11210505011 (standard reference, not re-checked)',
              'Ren, B. and Duncan, I.J. (2019). Reservoir simulation of carbon storage associated '
              'with CO2 EOR in residual oil zones, San Andres formation of West Texas, Permian '
              'Basin, USA. Energy 167, 391-401. https://doi.org/10.1016/j.energy.2018.11.007',
              'GCCC/BEG Woodbine and Paluxy data pages (see porosity).']},
 {'key': 'iz_t',
  'unit': 'F/100 ft',
  'typical': [1.2, 2.0],
  'plausible': [0.8, 3.5],
  'seen': 'about 0.5 to 1.9 F per 100 ft above 70 F (median 1.3)',
  'gradient': 'temperature',
  'if_missing': 'Fit (corrected) bottom-hole temperatures from nearby log headers against depth; '
                'or use the BEG/SMU temperature-at-depth maps. 1 C/km = 0.0549 F/100 ft. Mean '
                'surface temperature is 62 to 74 F in Texas (NOAA normals). Texas Gulf Coast '
                'normally pressured section about 1.4 to 1.8 F/100 ft (Frio pilot: about 153 F at '
                'about 4,900 ft, about 1.7 F/100 ft); gradients rise to 2.5 to 3+ F/100 ft inside '
                'geopressured shales. Permian Basin: Central Basin Platform about 1.0 to 1.4 F/100 '
                'ft (low heat flow, below 65 mW/m2); Delaware Basin about 1.4 to 2.0 modern, '
                'higher in the west.',
  'sources': ['SMU Geothermal Laboratory, Data and Maps. '
              'https://www.smu.edu/dedman/academics/departments/earth-sciences/research/geothermallab/datamaps',
              'BEG (2025). Onshore Gulf Coast Texas temperature at 3 km and depth to 150 C maps. '
              'https://store.beg.utexas.edu/product/3973',
              'Kharaka, Y.K. et al. (2006). Gas-water-rock interactions in Frio Formation '
              'following CO2 injection. Geology 34(7), 577-580. https://doi.org/10.1130/G22357.1',
              'Pecos County geothermal study, UT Austin repository. '
              'https://repositories.lib.utexas.edu/items/01be6734-86ac-4892-a3f2-1c5e362b3409',
              'AAPG Wiki, Geothermal gradient. https://wiki.aapg.org/Geothermal_gradient',
              'NOAA NCEI U.S. Climate Normals 1991-2020. '
              'https://www.ncei.noaa.gov/products/land-based-station/us-climate-normals (standard '
              'reference, not re-checked)']},
 {'key': 'iz_s',
  'unit': 'ppm',
  'typical': [30000, 150000],
  'plausible': [10000, 300000],
  'seen': '59,000 to 200,000 ppm (median 115,000)',
  'gradient': '',
  'if_missing': 'Use water analyses from nearby wells in the same formation (RRC records, USGS '
                'Produced Waters Geochemical Database) or estimate from SP/resistivity logs (Rw). '
                'Note anything below 10,000 mg/L would make the zone a USDW. Gulf Coast Frio and '
                'Miocene: 30,000 to 120,000 ppm typical (Frio pilot about 93,000 to 100,000 mg/L; '
                'upper-coast Frio above 80,000 mg/L, middle coast below 80,000); can exceed '
                '200,000 near salt domes; Na-acetate waters in shale-rich geopressured sections '
                'can be under 20,000. Permian: San Andres 26,000 to 62,000 mg/L on the Central '
                'Basin Platform; Devonian median about 154,000 mg/L basin-wide; produced waters '
                '100,000 to 200,000 mg/L.',
  'sources': ['Kharaka, Y.K. et al. (2005). Frio brine pilot abstract (AAPG Annual). '
              'https://www.searchanddiscovery.com/abstracts/html/2005/annual/abstracts/kharaka.htm',
              'Morton, R.A. et al. (1981). BEG Contract Report, Frio formation waters. '
              'https://www.beg.utexas.edu/files/publications/cr/CR1981-Morton-1_QAe6863.pdf',
              'Morton, R.A. and Land, L.S. (1987). Regional variations in formation water '
              'chemistry, Frio Formation (Oligocene), Texas Gulf Coast. AAPG Bulletin 71(2), '
              '191-206. (standard reference, not re-checked)',
              'Engle, M.A. et al. (2016). Geochemistry of formation waters from the Wolfcamp and '
              'Cline shales... Permian Basin. https://pubs.usgs.gov/publication/70177910 ; USGS '
              'Permian brine study https://www.usgs.gov/node/74614',
              'Stueber, A.M., Saller, A.H., Ishida, H. (1998). Origin, migration, and mixing of '
              'brines in the Permian Basin. AAPG Bulletin 82(9), 1652-1672. '
              'https://archives.datapages.com/data/bulletns/1998/09sep/1652/1652.htm']},
 {'key': 'iz_p',
  'unit': 'psi/ft',
  'typical': [0.433, 0.47],
  'plausible': [0.25, 0.95],
  'seen': '0.44 to 0.47 psi/ft (median 0.453); one depleted or over-pressured case outside',
  'gradient': 'pressure',
  'if_missing': 'Use DST, RFT/MDT, or shut-in BHP from nearby wells divided by depth. Lacking '
                'data, assume 0.465 psi/ft above top of geopressure on the Gulf Coast and verify '
                'the zone is not depleted (old fields) or overpressured. Gulf Coast normal '
                '(hydrostatic brine) about 0.465 psi/ft (100,000 ppm water). Top of geopressure on '
                'the Texas coast is generally 8,000 to 12,000 ft (Frio overpressure generally '
                'below about 7,000 ft on the upper coast; about 10,000 ft or 3,000 m in Lavaca '
                'County); gradients there 0.6 to 0.9, up to about 1.0 psi/ft. Permian: San Andres '
                'often near or below hydrostatic (0.30 to 0.44) due to production depletion; '
                'Delaware Basin Wolfcamp is overpressured (0.5 to 0.7), but that is not a typical '
                'storage zone. Woodbine is depleted from production.',
  'sources': ['AAPG Wiki, Normal hydrostatic pressure gradients. '
              'https://wiki.aapg.org/Normal_hydrostatic_pressure_gradients',
              'Bebout, D.G., Loucks, R.G., Gregory, A.R. (1978). Frio sandstone reservoirs in the '
              'deep subsurface along the Texas Gulf Coast. BEG Report of Investigations 91; and '
              'BEG Geothermal Resources, Frio Formation reports '
              'https://www.beg.utexas.edu/publications/330',
              'Properties of Geopressured Brines and Wells in the Gulf Coast. OSTI 890511. '
              'https://www.osti.gov/biblio/890511']},
 {'key': 'iz_cr',
  'unit': '1/psi',
  'typical': [3e-06, 1.5e-05],
  'plausible': [1e-06, 0.0001],
  'seen': '5e-6 to 3.4e-5 1/psi where stated',
  'gradient': '',
  'if_missing': 'Use Newman (1973) porosity correlation for the rock class, or Hall (1953) for '
                'consolidated rock. For shallow unconsolidated Gulf Coast sands use at least 1e-5. '
                'Consolidated sandstones 2e-6 to 2e-5 (typically 3e-6 to 6e-6). Friable and '
                'unconsolidated Gulf Coast Miocene/Pliocene sands 1e-5 to 1e-4. '
                'Limestones/dolomites 2e-6 to 1.5e-5. Hall (1953) correlation gives about 3e-6 to '
                '5e-6 at 20 to 30 percent porosity, which underestimates unconsolidated sands.',
  'sources': ['Newman, G.H. (1973). Pore-volume compressibility of consolidated, friable, and '
              'unconsolidated reservoir rocks under hydrostatic loading. JPT 25(2), 129-134. '
              'https://doi.org/10.2118/3835-PA',
              'Hall, H.N. (1953). Compressibility of reservoir rocks. Petroleum Transactions AIME '
              '198, 309-311. https://doi.org/10.2118/953309-G ; OneMine '
              'https://onemine.org/documents/technical-notes-compressibility-of-reservoir-rocks']},
 {'key': 'iz_dip',
  'unit': 'deg',
  'typical': [0.5, 3],
  'plausible': [0, 25],
  'seen': '0 to 2.9 degrees (median 0.8)',
  'gradient': '',
  'if_missing': 'Compute from the structure map (contour interval divided by contour spacing; dip '
                '= atan(dz/dx)). Lacking a map, use 1 degree gulfward for Gulf Coast and under 1 '
                'degree for Permian platform settings. Texas Gulf Coast Miocene/Frio regional dip '
                'about 0.5 to 2 degrees gulfward (roughly SE on the upper and middle coast, E to '
                'ESE in South Texas, i.e. perpendicular to the coast); steeper (3 to 10+ degrees) '
                'on growth-fault rollovers and salt-dome flanks. Permian San Andres on the Central '
                'Basin Platform and Northwest Shelf generally under 1 to 2 degrees; '
                'Delaware/Midland basin margins steeper. Convention: dip direction is the azimuth '
                'the bed slopes down toward, in degrees clockwise from north.',
  'sources': ['Galloway, W.E. (2008). Depositional evolution of the Gulf of Mexico sedimentary '
              'basin. In Sedimentary Basins of the World 5, 505-549. '
              'https://doi.org/10.1016/S1874-5997(08)00015-4 (standard reference, not re-checked)',
              'Ward, R.F., Kendall, C.G.St.C., Harris, P.M. (1986). Upper Permian (Guadalupian) '
              'facies and their association with hydrocarbons, Permian Basin. AAPG Bulletin 70(3), '
              '239-262. (standard reference, not re-checked)']},
 {'key': 'iz_az',
  'unit': 'deg',
  'typical': None,
  'plausible': [0, 360],
  'seen': '',
  'gradient': '',
  'if_missing': 'Read the dip direction off the structure map (down-dip, perpendicular to '
                'contours). Gulf Coast beds dip gulfward, roughly south-east to east (about 100 to '
                '160 degrees).',
  'sources': ['Galloway, W.E. (2008). Depositional evolution of the Gulf of Mexico sedimentary '
              'basin. In Sedimentary Basins of the World 5, 505-549. '
              'https://doi.org/10.1016/S1874-5997(08)00015-4 (standard reference, not re-checked)',
              'Ward, R.F., Kendall, C.G.St.C., Harris, P.M. (1986). Upper Permian (Guadalupian) '
              'facies and their association with hydrocarbons, Permian Basin. AAPG Bulletin 70(3), '
              '239-262. (standard reference, not re-checked)']},
 {'key': 'iz_kvkh',
  'unit': 'fraction',
  'typical': [0.01, 0.3],
  'plausible': [0.0001, 1.0],
  'seen': '0.03 to 1 (median 0.1)',
  'gradient': '',
  'if_missing': 'Use core plug kv/kh where available; otherwise use 0.1 for sands and treat the '
                'value as a sensitivity (0.01 and 0.5), since kv/kh controls gravity override and '
                'plume radius. Clean individual sands 0.1 to 0.5; interval-scale for interbedded '
                'Gulf Coast sand/shale 0.001 to 0.1 (0.1 is the most common modeling default). '
                'Carbonates 0.01 to 0.5, highly variable; fractured Ellenburger may approach 1.',
  'sources': ['Doughty, C. and Pruess, K. (2004). Modeling supercritical CO2 injection in '
              'heterogeneous porous media. Vadose Zone Journal 3(3), 837-847. '
              'https://doi.org/10.2136/vzj2004.0837 (standard reference, not re-checked)',
              'EPA (2013). Class VI AoR Evaluation and Corrective Action Guidance, EPA '
              '816-R-13-005 (Section 3, model parameters and sensitivity).']},
 {'key': 'cz',
  'unit': 'ft',
  'typical': [100, 1000],
  'plausible': [20, 3000],
  'seen': '94 to 2,312 ft (median 370)',
  'gradient': '',
  'if_missing': 'Measure from logs from the top of the injection zone to the top of the regional '
                'shale (exclude sandy stringers). 40 CFR 146.83 sets no minimum thickness; it '
                'requires a confining zone free of transmissive faults with sufficient areal '
                'extent, integrity and capillary entry pressure. Reviewers often look for a '
                'laterally continuous seal of at least about 100 ft plus secondary seals. Anahuac '
                'Shale (over Frio) about 100 to 1,000+ ft, thickening gulfward; Miocene '
                'intraformational shales 20 to 300 ft each, often stacked; Eagle Ford (over '
                'Woodbine) about 50 to 400 ft; Woodford (over Devonian/Fusselman) about 50 to 600 '
                'ft; San Andres seals are tight carbonates/anhydrites of Grayburg/Seven Rivers, '
                '100 to 500 ft.',
  'sources': ['40 CFR 146.83 Minimum criteria for siting. '
              'https://www.ecfr.gov/current/title-40/chapter-I/subchapter-D/part-146/subpart-H/section-146.83 '
              '(standard reference, not re-checked)',
              'Swanson, S.M. et al. (2013). Geologic assessment of the Anahuac and Frio... USGS; '
              'and GCCC Oligocene data pages https://gccc.beg.utexas.edu/co2-data/oligocene-12c '
              '(standard reference, not re-checked)',
              'GCCC Woodbine overview. https://gccc.beg.utexas.edu/node/93']},
 {'key': 'usdw_base',
  'unit': 'ft',
  'typical': [500, 4500],
  'plausible': [0, 7000],
  'seen': '150 to 3,000 ft (median 1,440)',
  'gradient': '',
  'if_missing': 'Do not estimate if a GAU letter exists; use the letter. Without one, interpret '
                'resistivity logs (Rw corresponding to 10,000 mg/L) at nearby wells and compare '
                'with TWDB BRACS brackish aquifer maps. USDW = aquifer with TDS below 10,000 mg/L '
                '(40 CFR 144.3). Gulf Coast Aquifer system: base of USDW commonly 1,500 to 4,500 '
                'ft inland, shallower near the coast (a few hundred to about 2,000 ft). Permian '
                'Basin: commonly 300 to 2,500 ft (Santa Rosa/Dockum, Capitan Reef where present, '
                'Rustler locally). Offshore state waters: may be very shallow or absent. The RRC '
                'Groundwater Advisory Unit GW-2 letter is the controlling source; it states both '
                'the base of usable-quality water (BUQW, about 3,000 mg/L) and base of USDW '
                '(10,000 mg/L).',
  'sources': ['40 CFR 144.3 Definitions (USDW). '
              'https://www.ecfr.gov/current/title-40/chapter-I/subchapter-D/part-144/subpart-A/section-144.3 '
              '(standard reference, not re-checked)',
              'RRC Groundwater Advisory Unit. '
              'https://www.rrc.texas.gov/oil-and-gas/applications-and-permits/groundwater-advisory-unit',
              'Harcourt, J. RRC GAU presentation, Filing and interpreting groundwater letters '
              'GW-1/GW-2. '
              'https://rrc.texas.gov/media/jvsb3a1r/filing-and-interpreting-groundwater-letters-gw-1-gw-2-james-harcourt.pdf',
              'TWDB Brackish Resources Aquifer Characterization System (BRACS) reports, e.g. Gulf '
              'Coast Aquifer. https://www.twdb.texas.gov/innovativewater/bracs/ (standard '
              'reference, not re-checked)']},
 {'key': 'usdw_p',
  'unit': 'psi/ft',
  'typical': [0.433, 0.44],
  'plausible': [0.35, 0.45],
  'seen': 'about 0.433 psi/ft times the USDW base depth',
  'gradient': 'pressure',
  'if_missing': 'Use 0.433 psi/ft times depth, or better, the measured static water level '
                '(pressure = 0.433 x (depth - depth to water)). Fresh water 0.433 psi/ft; water at '
                '10,000 mg/L about 0.436 psi/ft. Artesian or drawn-down aquifers '
                '(Houston/Galveston subsidence area, Permian irrigated areas) may be below '
                'hydrostatic.',
  'sources': ['AAPG Wiki, Normal hydrostatic pressure gradients. '
              'https://wiki.aapg.org/Normal_hydrostatic_pressure_gradients']},
 {'key': 'usdw_t',
  'unit': 'degF',
  'typical': [70, 110],
  'plausible': [55, 140],
  'seen': '',
  'gradient': '',
  'if_missing': 'Surface temperature + gradient x USDW base depth / 100. Mean surface temperature '
                'plus gradient to USDW depth: Gulf Coast about 75 to 110 F at 1,000 to 3,000 ft; '
                'Permian about 65 to 85 F at 300 to 2,000 ft.',
  'sources': ['Derived from surface temperature and geothermal gradient rows above.']},
 {'key': 'usdw_s',
  'unit': 'ppm',
  'typical': [1000, 10000],
  'plausible': [0, 10000],
  'seen': '',
  'gradient': '',
  'if_missing': 'The base of the USDW is by definition where water reaches 10,000 mg/L TDS, so use '
                'a value near 10,000 ppm at the base unless the GAU letter or a water analysis '
                'says otherwise.',
  'sources': ['40 CFR 144.3 Definitions (USDW). '
              'https://www.ecfr.gov/current/title-40/chapter-I/subchapter-D/part-144/subpart-A/section-144.3 '
              '(standard reference, not re-checked)',
              'RRC Groundwater Advisory Unit. '
              'https://www.rrc.texas.gov/oil-and-gas/applications-and-permits/groundwater-advisory-unit',
              'Harcourt, J. RRC GAU presentation, Filing and interpreting groundwater letters '
              'GW-1/GW-2. '
              'https://rrc.texas.gov/media/jvsb3a1r/filing-and-interpreting-groundwater-letters-gw-1-gw-2-james-harcourt.pdf']},
 {'key': 'water_depth',
  'unit': 'ft',
  'typical': [10, 80],
  'plausible': [0, 120],
  'seen': '',
  'gradient': '',
  'if_missing': 'Read from NOAA nautical charts or the NOAA Coastal Relief Model at the well '
                'location. Texas state waters extend 3 marine leagues (9 nautical miles, about '
                '10.36 statute miles) from shore. The inner shelf is gentle: about 30 m (100 ft) '
                'isobath lies about 16 miles off Port Aransas, so the state-waters line is mostly '
                'in about 50 to 90 ft of water off the middle/south coast and about 40 to 70 ft '
                'off Galveston. Bays and passes are 5 to 50 ft.',
  'sources': ['Texas GLO, Three Marine League Line. '
              'https://www.glo.texas.gov/maps/three-marine-league-line',
              'RRC county/offshore map. '
              'https://rrc.texas.gov/media/gembj3er/cty_coast_offshore.pdf',
              'USGS Open-File Report 75-218 (Port Aransas inner shelf). '
              'https://pubs.usgs.gov/of/1975/0218/report.pdf',
              'NOAA NCEI U.S. Coastal Relief Model. '
              'https://www.ncei.noaa.gov/products/coastal-relief-model (standard reference, not '
              're-checked)']},
 {'key': 'off_t',
  'unit': 'degF',
  'typical': [60, 84],
  'plausible': [50, 90],
  'seen': '',
  'gradient': '',
  'if_missing': 'Use 73 F annual mean as the top boundary temperature for offshore geothermal '
                'gradient calculations. Inner Texas shelf bottom water is well mixed and follows '
                'season: about 57 to 64 F in winter to 82 to 86 F in late summer; annual mean '
                'about 72 to 75 F.',
  'sources': ['Texas A&M monthly NW Gulf shelf temperature study 1963-1965 (station depths 7 to 73 '
              'm). https://tamug-ir.tdl.org/items/83777b0e-3581-4413-9a12-736a7fb5f34e/full',
              'NOAA NDBC buoys (e.g. 42019, 42020, 42035) water temperature records. '
              'https://www.ndbc.noaa.gov/ (standard reference, not re-checked)']},
 {'key': 'swr',
  'unit': 'fraction',
  'typical': [0.15, 0.4],
  'plausible': [0.05, 0.7],
  'seen': '0.06 to 0.45 (median 0.25)',
  'gradient': '',
  'if_missing': 'Use mercury injection/capillary pressure or air-brine Pc curves; or adopt a value '
                'from Krevor et al. (2012)/Bennion and Bachu (2008) for a similar lithology and '
                'permeability, then test sensitivity. Clean high-perm Gulf Coast sands 0.1 to 0.3; '
                'lower-perm and carbonates 0.3 to 0.6. Unsteady-state lab values (Bennion and '
                'Bachu) often 0.3 to 0.6 because achievable capillary pressure was limited; true '
                'Swr is lower.',
  'sources': ['Bennion, D.B. and Bachu, S. (2008). Drainage and imbibition relative permeability '
              'relationships for supercritical CO2/brine and H2S/brine systems in intergranular '
              'sandstone, carbonate, shale, and anhydrite rocks. SPE Reservoir Evaluation and '
              'Engineering 11(3), 487-496. https://doi.org/10.2118/99326-PA',
              'Krevor, S.C.M., Pini, R., Zuo, L., Benson, S.M. (2012). Relative permeability and '
              'trapping of CO2 and water in sandstone rocks at reservoir conditions. Water '
              'Resources Research 48, W02532. https://doi.org/10.1029/2011WR010859',
              'Burnside, N.M. and Naylor, M. (2014). Review and implications of relative '
              'permeability of CO2/brine systems and residual trapping of CO2. IJGGC 23, 1-11. '
              'https://doi.org/10.1016/j.ijggc.2014.01.013']},
 {'key': 'sgr',
  'unit': 'fraction',
  'typical': [0.1, 0.35],
  'plausible': [0.0, 0.5],
  'seen': '0.01 to 0.34 (median 0.25)',
  'gradient': '',
  'if_missing': 'Use 0.2 to 0.3 for Gulf Coast sands with a Land trapping model if hysteresis is '
                'simulated; for a non-hysteretic model use a conservative low value (0.05 to 0.1) '
                'for plume extent so trapping does not shrink the plume artificially. Sandstones '
                'commonly 0.1 to 0.35 at maximum initial CO2 saturation; Burnside and Naylor '
                'report 13 to 92 percent of injected CO2 can be residually trapped across '
                'sandstone experiments. Depends on initial saturation (hysteresis, Land model).',
  'sources': ['Krevor et al. (2012), WRR 48. https://doi.org/10.1029/2011WR010859',
              'Burnside and Naylor (2014), IJGGC 23, 1-11. '
              'https://doi.org/10.1016/j.ijggc.2014.01.013',
              'Pini, R., Krevor, S.C.M., Benson, S.M. (2012). Capillary pressure and heterogeneity '
              'for the CO2/water system in sandstone rocks at reservoir conditions. Advances in '
              'Water Resources 38, 48-59. https://doi.org/10.1016/j.advwatres.2011.12.007 '
              '(standard reference, not re-checked)']},
 {'key': 'krg0',
  'unit': 'fraction',
  'typical': [0.2, 0.6],
  'plausible': [0.05, 1.0],
  'seen': '0.1 to 1.0 (median 0.53)',
  'gradient': '',
  'if_missing': 'Use 0.3 to 0.5 for screening; run a sensitivity because a low krg0 makes the '
                'plume compact and a high one widens it. Bennion and Bachu lab values 0.1 to 0.54 '
                '(lower for high-perm rock). Krevor/Benson argue the true endpoint at Swr is '
                'higher (0.6 to 1.0) because lab floods did not reach Swr.',
  'sources': ['Bennion and Bachu (2008), SPE REE 11(3). https://doi.org/10.2118/99326-PA',
              'Benson, S., Pini, R., Reynolds, C., Krevor, S. (2013). Relative permeability '
              'analyses to describe multi-phase flow in CO2 storage reservoirs. Global CCS '
              'Institute Targeted Report 2. '
              'https://www.globalccsinstitute.com/resources/publications-reports-research/relative-permeability-analysis-to-describe-multi-phase-flow-in-co2-storage-reservoirs/']},
 {'key': 'krw0',
  'unit': 'fraction',
  'typical': [0.8, 1.0],
  'plausible': [0.3, 1.0],
  'seen': '0.8 to 1.0',
  'gradient': '',
  'if_missing': 'Use 1.0 for drainage (plume growth). Brine is the wetting phase; krw at Sw = 1 is '
                '1.0 by definition. Imbibition endpoint at Sgr is lower (0.3 to 0.8).',
  'sources': ['Krevor et al. (2012), WRR 48. https://doi.org/10.1029/2011WR010859']},
 {'key': 'corey_w',
  'unit': '-',
  'typical': [2, 6],
  'plausible': [1, 10],
  'seen': '2 to 5 (median 3.5)',
  'gradient': '',
  'if_missing': 'Use 4 (Brooks-Corey with lambda about 1 to 2 gives nw about 3 to 4). Fitted brine '
                'exponents in CO2-brine sandstones commonly 3 to 6; 4 is a frequent default.',
  'sources': ['Krevor et al. (2012), WRR 48. https://doi.org/10.1029/2011WR010859',
              'Brooks, R.H. and Corey, A.T. (1964). Hydraulic properties of porous media. '
              'Hydrology Papers 3, Colorado State University. (standard reference, not '
              're-checked)']},
 {'key': 'corey_g',
  'unit': '-',
  'typical': [2, 5],
  'plausible': [1, 8],
  'seen': '1.8 to 3 (median 2.4)',
  'gradient': '',
  'if_missing': 'Use 2 to 3. Fitted CO2 exponents commonly 1.5 to 4; 2 to 3 typical.',
  'sources': ['Krevor et al. (2012), WRR 48. https://doi.org/10.1029/2011WR010859',
              'Bennion and Bachu (2008), SPE REE 11(3).']},
 {'key': 'threshold',
  'unit': 'psi',
  'typical': [0, 300],
  'plausible': [-500, 2000],
  'seen': '39 to 313 psi (median 108)',
  'gradient': '',
  'if_missing': 'Compute with the EPA equation from USDW base depth, injection-zone top, brine '
                'density (from salinity and temperature) and initial pressure. If negative, the '
                'AoR becomes the full pressure-front extent (or the plume, if pressure decline '
                'returns below it) and the reviewer should check the initial pressure input. EPA '
                '(2013) open-borehole method: dPc = Pu + rho_i g (zu - zi) - Pi, i.e. the pressure '
                'needed in the injection zone to lift injection-zone brine through an open conduit '
                'to the base of the USDW, minus initial pressure (Nicot et al. 2009 add linear '
                'density variation along the borehole). When initial pressure is hydrostatic with '
                'a fresh-water gradient to the USDW and brine below, dPc is roughly (rho_brine - '
                'rho_fresh) gradient x height between USDW base and injection top, e.g. (0.465 - '
                '0.433) x 3,000 ft = about 100 psi. It can be near zero or negative where '
                'formations are overpressured, and large where the zone is depleted. Reported AoR '
                'thresholds: some applications use about 10 psi; many Gulf Coast and Permian applications '
                'report tens to a few hundred psi. Mud-column method (Texas practice with '
                'plugged/abandoned wells): adds mud weight overbalance and gel strength, giving '
                'dPc of hundreds to over 1,000 psi.',
  'sources': ['EPA (2013). Geologic Sequestration of Carbon Dioxide, UIC Program Class VI Well '
              'Area of Review Evaluation and Corrective Action Guidance. EPA 816-R-13-005. '
              'https://www.epa.gov/sites/default/files/2015-07/documents/epa816r13005.pdf',
              'Nicot, J.-P., Oldenburg, C.M., Bryant, S.L., Hovorka, S.D. (2009). Pressure '
              'perturbations from geologic carbon sequestration: area-of-review boundaries and '
              'borehole leakage driving forces. Energy Procedia 1(1), 47-54. '
              'https://doi.org/10.1016/j.egypro.2009.01.009 ; '
              'https://escholarship.org/uc/item/8kg0c865']},
 {'key': 'ppg',
  'unit': 'ppg',
  'typical': [9.0, 10.5],
  'plausible': [8.4, 18],
  'seen': '',
  'gradient': '',
  'if_missing': 'Use the mud weight on the well log header (MW at TD) for each abandoned well; if '
                'unknown, assume 9.0 ppg (slightly above 0.465 brine gradient). Wells are commonly '
                'drilled at about 200 psi or more overbalance; older Gulf Coast and Permian wells '
                'in normally pressured sections typically 9 to 10.5 ppg; geopressured Gulf Coast '
                'wells 12 to 18 ppg. Gradient = 0.052 x ppg (9.0 ppg = 0.468 psi/ft). Mud left in '
                'abandoned wells may settle, degrade, or be displaced, so reviewers should use the '
                'lowest credible weight (often 9.0 ppg or the documented weight) and EPA has '
                'questioned reliance on it without field verification.',
  'sources': ['EPA Compendium of Technical Studies (EAB docket). '
              'https://yosemite.epa.gov/oa/eab_web_docket.nsf/Attachments%20By%20ParentFilingId/C788ED89EF58FF4C852588EC00425F8D/$FILE/Compendium%20of%20Technical%20Studies.pdf',
              'Oil well control (0.052 x ppg). https://en.wikipedia.org/wiki/Oil_well_control']},
 {'key': 'gel',
  'unit': 'psi',
  'typical': [0, 60],
  'plausible': [0, 200],
  'seen': '',
  'gradient': '',
  'if_missing': 'Gel strength is reported in lbf/100 ft2 (typically 5 to 30). Containment wants '
                'the pressure it adds: psi = gel x column length (ft) / (300 x hole diameter '
                '(in)), e.g. 10 lbf/100 ft2 over 5,000 ft in an 8 in hole is about 21 psi. Use 0 '
                '(most protective) unless the operator documents it.',
  'sources': ['EPA Compendium of Technical Studies (see mud_weight).',
              'Bourgoyne, A.T., Millheim, K.K., Chenevert, M.E., Young, F.S. (1986). Applied '
              'Drilling Engineering. SPE Textbook Series Vol. 2. (standard reference, not '
              're-checked)']},
 {'key': 'rate',
  'unit': 'MMT/yr',
  'typical': [0.3, 1.5],
  'plausible': [0.02, 5],
  'seen': '0.15 to 2.0 MMT/yr per well (median 1.0)',
  'gradient': '',
  'if_missing': 'Divide project rate by the number of injectors; check against injectivity (kh) '
                'and the 90 percent fracture-pressure limit. Permitted Texas, Louisiana and Illinois '
                'Class VI wells are mostly about 0.75 to 1.4 Mt/yr per well. High-perm '
                'Gulf Coast sands can support 2+ Mt/yr per well; Permian carbonates generally '
                'under 1.',
  'sources': ['RRC CO2 storage notices. '
              'https://rrc.texas.gov/oil-and-gas/applications-and-permits/injection-storage-permits/co2-storage/co2-notices',
              'Louisiana Class VI permit status. '
              'https://www.dce.louisiana.gov/assets/OPC-ClassVI/Louisiana-Class-VI-Permit-Status.pdf']},
 {'key': 'brine_rate',
  'unit': 'bbl/day',
  'typical': [2000, 20000],
  'plausible': [100, 50000],
  'seen': '2,500 to 8,500 bbl/day per well (two applications)',
  'gradient': '',
  'if_missing': "Derive from the operator's stated volume-replacement target: rate (bbl/d) = "
                'fraction x CO2 mass rate / CO2 reservoir density / 0.159 / 365. Pressure '
                'management wells are usually sized to remove a volume comparable to a fraction '
                '(often 25 to 100 percent) of injected reservoir volume. 1 Mt/yr CO2 at about 0.65 '
                'to 0.75 g/cc is about 23,000 to 26,000 reservoir bbl/day, so a single extractor '
                'matching half of one injector is about 10,000 to 13,000 bbl/day. Gulf Coast '
                'salt-water disposal wells commonly take 5,000 to 30,000 bbl/day, a practical '
                'analog for achievable rates.',
  'sources': ['Buscheck, T.A. et al. (2012). Active CO2 reservoir management for carbon storage: '
              'Analysis of operational strategies to relieve pressure buildup and improve '
              'injectivity. IJGGC 6, 230-245. https://doi.org/10.1016/j.ijggc.2011.11.007',
              'Birkholzer, J.T., Cihan, A., Zhou, Q. (2012). Impact-driven pressure management via '
              'targeted brine extraction. IJGGC 7, 168-180. '
              'https://doi.org/10.1016/j.ijggc.2012.01.001 (standard reference, not re-checked)',
              'Gonzalez-Nicolas, A. et al. (2019). Pressure management via brine extraction in '
              'geological CO2 storage: adaptive optimization strategies under poorly characterized '
              'reservoir conditions. IJGGC 83, 176-185.']},
 {'key': 'max_bhp',
  'unit': 'psi/ft',
  'typical': [0.585, 0.765],
  'plausible': [0.45, 0.95],
  'seen': '',
  'gradient': 'pressure',
  'if_missing': '90 percent of the fracture pressure at the top perforation (40 CFR 146.88(a)). '
                'Fracture gradients are typically 0.65 to 0.85 psi/ft; Use step-rate test, '
                "leak-off test or minifrac data; otherwise Eaton (1969) with log-derived Poisson's "
                'ratio and overburden. Many Gulf Coast applications default to about 0.7 psi/ft.',
  'sources': ['Eaton, B.A. (1969). Fracture gradient prediction and its application in oilfield '
              'operations. JPT 21(10), 1353-1360. https://doi.org/10.2118/2163-PA',
              '40 CFR 146.88(a) Injection well operating requirements. '
              'https://www.ecfr.gov/current/title-40/chapter-I/subchapter-D/part-146/subpart-H/section-146.88 '
              '(standard reference, not re-checked)',
              'Matthews, W.R. and Kelly, J. (1967). How to predict formation pressure and fracture '
              'gradient. Oil and Gas Journal 65, 92-106. (standard reference, not re-checked)']},
 {'key': 'radius',
  'unit': 'ft',
  'typical': [0.3, 0.5],
  'plausible': [0.1, 1.0],
  'seen': '',
  'gradient': '',
  'if_missing': 'Half the bit size across the injection zone, in ft (e.g. 8.5 in bit gives 0.354 '
                'ft). Class VI wells commonly have 7 in or 9-5/8 in long-string casing in 8-1/2 in '
                'to 12-1/4 in hole: rw = 0.35 to 0.51 ft (bit) or 0.29 to 0.40 ft (casing OD).',
  'sources': ['RRC/EPA Class VI well construction schematics (typical); API Spec 5CT casing sizes. '
              '(standard reference, not re-checked)']},
 {'key': 'open_h',
  'unit': 'ft',
  'typical': [20, 200],
  'plausible': [5, 500],
  'seen': '30 to 216 ft per stage (one application)',
  'gradient': '',
  'if_missing': 'Use the perforated net sand thickness of each stage from the completion diagram. '
                'Gulf Coast stacked Miocene/Frio designs inject into several sands; each completed '
                'sand or stage is typically 20 to 200 ft of perforated net sand. DOE project '
                'DE-FE0010554 modeled sequential injection into two and four stacked reservoirs.',
  'sources': ['DOE/NETL project FE0010554, stacked storage in Gulf Coast. '
              'https://netl.doe.gov/sites/default/files/Carbon_Storage/Retired/FE0010554.pdf']},
 {'key': 'cutoff',
  'unit': 'fraction',
  'typical': [0.01, 0.05],
  'plausible': [0.001, 0.1],
  'seen': '0.001 to 0.05 (median 0.01)',
  'gradient': '',
  'if_missing': 'Use 0.01. Most EPA-reviewed Class VI AoRs use the 1 percent (0.01) free-phase CO2 '
                'saturation isoline. Some use a mole-fraction '
                'cutoff (0.01). Larger cutoffs (5 percent) make the plume smaller and should be '
                'justified.',
  'sources': ['Kansas Geological Survey OFR 2016-29 (Wellington Class VI). '
              'https://www.kgs.ku.edu/Publications/OFR/2016/OFR16_29/index.html']},
 {'key': 'end_year',
  'unit': 'yr',
  'typical': None,
  'plausible': [10, 1000],
  'seen': '58 to 200 years (median 70)',
  'gradient': '',
  'if_missing': 'Injection years plus at least the 50-year default PISC period (40 CFR 146.93), '
                'and longer if the plume is still moving at the end.',
  'sources': ['40 CFR 146.93 Post-injection site care and site closure. '
              'https://www.ecfr.gov/current/title-40/chapter-I/subchapter-D/part-146/subpart-H/section-146.93 '
              '(standard reference, not re-checked)',
              '16 TAC 5.206 (Texas RRC Chapter 5) post-injection storage facility care. (standard '
              'reference, not re-checked)']},
 {'key': 'cell',
  'unit': 'ft',
  'typical': [250, 1000],
  'plausible': [20, 5000],
  'seen': '',
  'gradient': '',
  'if_missing': 'Start with 500 ft; Containment warns if the plume is fewer than 20 cells across, '
                'and then use a smaller cell.',
  'sources': ['EPA (2013). Class VI Well Area of Review Evaluation and Corrective Action Guidance, '
              'EPA 816-R-13-005, Section 2.3 (grid resolution).']},
 {'key': 'engine', 'unit': '-', 'typical': None, 'plausible': None,
  'seen': 'all 15 rebuilt applications were run on ve, as their operators used 3-D numerical models',
  'gradient': '',
  'if_missing': 'Use ve. EPA expects the AoR from computational modelling that accounts for the physical and chemical properties of the injected CO2 and the formation (40 CFR 146.84(c)); the analytical engine is a screening check.',
  'sources': ['40 CFR 146.84(c), computational modelling of the AoR',
              'EPA (2013). Class VI Well Area of Review Evaluation and Corrective Action Guidance, EPA 816-R-13-005, Sections 2.2 to 2.3 (model selection; analytical models as a comparative check)',
              'Nordbotten, J.M. and Celia, M.A. (2012). Geological Storage of CO2: Modeling Approaches for Large-Scale Simulation. Wiley (vertical-equilibrium models)']},
 {'key': 'method', 'unit': '-', 'typical': None, 'plausible': None,
  'seen': 'Method 1 in most applications; Method 3 (mud column), the Nicot method and a negative Method 1 in one each',
  'gradient': '',
  'if_missing': 'Use auto. Where the application states a threshold, compare it with the methods in the Threshold panel and ask how it was derived; give it as threshold.override only to reproduce the operator.',
  'sources': ['EPA (2013). EPA 816-R-13-005, Section 3.4.1 (threshold pressure methods, over-pressured cases)',
              'Thornhill, J.T. et al. (1982). Examination of the Area of Review concept. EPA',
              'Nicot, J.-P., Oldenburg, C.M., Bryant, S.L. and Hovorka, S.D. (2009). Pressure perturbations from geologic carbon sequestration: area-of-review boundaries and borehole leakage driving forces. Energy Procedia 1, 47-54',
              'Johnston, O.C. and Knape, B.K. (1986). Pressure effects of the static mud column in abandoned wells. Texas Water Commission (Class I practice)']}]
