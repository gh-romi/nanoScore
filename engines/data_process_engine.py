import json
import copy
import html

class DataProcessEngine:
    """
    A unified engine to process JSON data through various music theory and synchronization stages.
    """
    # --- 1. Class ID Mappings ---
    ACCIDENTALS = {0, 1, 2}
    BARLINES = {3, 4, 23}
    CLEFS = {7, 8, 9}
    NOTES = {5, 15, 16, 17, 18, 19, 20, 21, 22}
    RESTS = {24, 25, 26, 27, 28, 29, 30}
    TIMES = {11, 12, 32, 33}

    ID_TO_RHYTHM = {
        5: "note_breve", 15: "note_longa", 16: "note_maxima",
        17: "note_eighth", 18: "note_half", 19: "note_quarter",
        20: "note_sixteenth", 21: "note_whole", 22: "note_whole",  # Colored is handled via modifier
        24: "note_breve", 25: "note_eighth", 26: "note_half",
        27: "note_longa", 28: "note_quarter", 29: "note_sixteenth",
        30: "note_whole"
    }

    ID_TO_NAME = {
        0: "flat", 1: "natural", 2: "sharp",
        3: "barline", 4: "barline_double", 23: "repeat",
        6: "cadence_point", 13: "dot", 14: "fermata", 31: "tie_slur",
        11: "digit_2", 12: "digit_3", 32: "time_C", 33: "time_cut"
    }

    # --- 2. Coordinate Extraction Helpers ---
    @staticmethod
    def _get_bbox(sym):
        return sym.get("symbol_box_absolute_xyxy", [0, 0, 0, 0])

    @classmethod
    def _get_x_center(cls, sym):
        if "symbol_box_relative_xywh" in sym:
            return sym["symbol_box_relative_xywh"][0]
        bbox = cls._get_bbox(sym)
        return (bbox[0] + bbox[2]) / 2.0

    @classmethod
    def _get_y_center(cls, sym):
        if "symbol_box_relative_xywh" in sym:
            return sym["symbol_box_relative_xywh"][1]
        bbox = cls._get_bbox(sym)
        return (bbox[1] + bbox[3]) / 2.0

    @classmethod
    def _get_x_min(cls, sym): return cls._get_bbox(sym)[0]

    @classmethod
    def _get_x_max(cls, sym): return cls._get_bbox(sym)[2]

    @classmethod
    def _get_y_min(cls, sym): return cls._get_bbox(sym)[1]

    @classmethod
    def _get_y_max(cls, sym): return cls._get_bbox(sym)[3]

    @staticmethod
    def _overlaps_1d(min1, max1, min2, max2):
        return max(min1, min2) <= min(max1, max2)

    # --- 3. JSON Staff Extractor ---
    @staticmethod
    def _extract_staves_and_symbols(data):
        staves = []
        for page in data.get("pages", []):
            p_id = page.get("page_id")
            for staff in page.get("staves", []):
                s_id = staff.get("staff_number")
                if "symbols" in staff:
                    staves.append({
                        "page_id": p_id,
                        "staff_number": s_id,
                        "symbols": staff["symbols"]
                    })
        return staves

    # --- 4. Main Semantic Engine ---
    def process_agnostic_to_partially_semantic(self, agnostic_data):
        staves = self._extract_staves_and_symbols(agnostic_data)

        semantic_measures = []
        current_measure_events = []
        global_measure_number = 1

        current_measure_page = None
        current_measure_staff = None

        for staff_data in staves:
            raw_symbols = staff_data["symbols"]
            p_id = staff_data["page_id"]
            s_id = staff_data["staff_number"]

            # Filter out custos and sort by X-center
            staff_symbols = [s for s in raw_symbols if s.get("class_id") != 10]
            staff_symbols.sort(key=lambda s: self._get_x_center(s))

            # A. Clean Duplicate Clefs
            cleaned_symbols = []
            skip_next = False
            for i in range(len(staff_symbols)):
                if skip_next:
                    skip_next = False
                    continue
                s1 = staff_symbols[i]
                if s1["class_id"] in self.CLEFS and i + 1 < len(staff_symbols):
                    s2 = staff_symbols[i + 1]
                    if s2["class_id"] in self.CLEFS:
                        c1_conf, c2_conf = s1.get("class_confidence", 1.0), s2.get("class_confidence", 1.0)
                        kept = s2 if (c1_conf >= 0.5 and c2_conf >= 0.5) else \
                            s2 if (c1_conf < 0.5 and c2_conf >= 0.5) else \
                                s1 if (c1_conf >= 0.5 and c2_conf < 0.5) else s2
                        cleaned_symbols.append(kept)
                        skip_next = True
                        continue
                cleaned_symbols.append(s1)

            staff_symbols = cleaned_symbols

            # --- Slur Spatial Inference Engine ---
            staff_notes = [s for s in staff_symbols if s["class_id"] in self.NOTES]
            for slur in staff_symbols:
                if slur["class_id"] == 31 and "symbol_box_absolute_xyxy" in slur:
                    s_xmin, s_xmax = self._get_x_min(slur), self._get_x_max(slur)

                    overlapped = [n for n in staff_notes if self._overlaps_1d(self._get_x_min(n), self._get_x_max(n), s_xmin, s_xmax)]

                    if len(overlapped) == 1:
                        n = overlapped[0]
                        n_xmin, n_xmax = self._get_x_min(n), self._get_x_max(n)

                        left_overhang = n_xmin - s_xmin
                        right_overhang = s_xmax - n_xmax
                        n_idx = staff_notes.index(n)

                        if right_overhang > left_overhang:
                            if n_idx + 1 < len(staff_notes):
                                next_n = staff_notes[n_idx + 1]
                                slur["symbol_box_absolute_xyxy"][2] = self._get_x_max(next_n)
                        else:
                            if n_idx - 1 >= 0:
                                prev_n = staff_notes[n_idx - 1]
                                slur["symbol_box_absolute_xyxy"][0] = self._get_x_min(prev_n)
            # ------------------------------------------

            current_clef_x_max = 0
            active_key_signature = []

            # B. Iterate over the cleaned staff symbols
            for i, sym in enumerate(staff_symbols):
                if current_measure_page is None:
                    current_measure_page = p_id
                    current_measure_staff = s_id

                cid = sym["class_id"]

                # ---------------------------------------------
                # BARLINES
                # ---------------------------------------------
                if cid in self.BARLINES:
                    if not current_measure_events and len(semantic_measures) > 0:
                        prev_rb = semantic_measures[-1]["right_barline"]
                        curr_rb = self.ID_TO_NAME[cid]
                        if curr_rb == "repeat" or (curr_rb == "barline_double" and prev_rb == "barline"):
                            semantic_measures[-1]["right_barline"] = curr_rb
                        continue

                    semantic_measures.append({
                        "measure_number": global_measure_number,
                        "right_barline": self.ID_TO_NAME[cid],
                        "page_id": current_measure_page,
                        "staff_number": current_measure_staff,
                        "events": current_measure_events
                    })
                    global_measure_number += 1
                    current_measure_events = []
                    current_measure_page = None
                    current_measure_staff = None

                # ---------------------------------------------
                # CLEFS
                # ---------------------------------------------
                elif cid in self.CLEFS:
                    current_clef_x_max = self._get_x_max(sym)
                    clef_sign = "C" if cid == 7 else "F" if cid == 8 else "G"
                    clef_event = {
                        "type": "clef",
                        "sign": clef_sign,
                        "line": 2 if clef_sign == "G" else sym.get("position_number")
                    }

                    next_target_idx = len(staff_symbols)
                    for j in range(i + 1, len(staff_symbols)):
                        if staff_symbols[j]["class_id"] in self.NOTES or staff_symbols[j]["class_id"] in self.RESTS or \
                                staff_symbols[j]["class_id"] in self.BARLINES or staff_symbols[j]["class_id"] in self.CLEFS or \
                                staff_symbols[j]["class_id"] in self.TIMES:
                            next_target_idx = j
                            break

                    target_x_min = self._get_x_min(staff_symbols[next_target_idx]) if next_target_idx < len(
                        staff_symbols) else float('inf')

                    for j in range(i + 1, next_target_idx):
                        acc = staff_symbols[j]
                        if acc["class_id"] in self.ACCIDENTALS:
                            if (self._get_x_min(acc) - current_clef_x_max) < (target_x_min - self._get_x_max(acc)):
                                active_key_signature.append({
                                    "type": self.ID_TO_NAME[acc["class_id"]],
                                    "position_type": acc.get("position_type"),
                                    "position_number": acc.get("position_number")
                                })

                    if active_key_signature: clef_event["key_signature"] = active_key_signature
                    current_measure_events.append(clef_event)

                # ---------------------------------------------
                # TIME SIGNATURES
                # ---------------------------------------------
                elif cid in self.TIMES:
                    time_event = {
                        "type": "time_signature",
                        "value": self.ID_TO_NAME[cid]
                    }
                    current_measure_events.append(time_event)

                # ---------------------------------------------
                # NOTES
                # ---------------------------------------------
                elif cid in self.NOTES:
                    note_event = {"type": "note", "class_id": cid, "position_type": sym.get("position_type"),
                                  "position_number": sym.get("position_number"), "modifiers": []}

                    note_x_min, note_x_max = self._get_x_min(sym), self._get_x_max(sym)
                    note_y_min, note_y_max = self._get_y_min(sym), self._get_y_max(sym)

                    prev_bound_idx = -1
                    for j in range(i - 1, -1, -1):
                        if staff_symbols[j]["class_id"] in self.NOTES or staff_symbols[j]["class_id"] in self.RESTS or \
                                staff_symbols[j]["class_id"] in self.BARLINES or staff_symbols[j]["class_id"] in self.CLEFS or \
                                staff_symbols[j]["class_id"] in self.TIMES:
                            prev_bound_idx = j
                            break

                    next_bound_idx = len(staff_symbols)
                    for j in range(i + 1, len(staff_symbols)):
                        if staff_symbols[j]["class_id"] in self.NOTES or staff_symbols[j]["class_id"] in self.RESTS \
                                or staff_symbols[j]["class_id"] in self.BARLINES or staff_symbols[j]["class_id"] in self.TIMES:
                            next_bound_idx = j
                            break

                    found_accidental = False
                    attached_accidentals = []

                    for j in range(prev_bound_idx + 1, i):
                        acc = staff_symbols[j]
                        if acc["class_id"] in self.ACCIDENTALS:
                            if (self._get_x_min(sym) - self._get_x_max(acc)) < (self._get_x_min(acc) - current_clef_x_max):
                                note_event["modifiers"].append(
                                    {"type": "accidental", "value": self.ID_TO_NAME[acc["class_id"]]})
                                attached_accidentals.append(acc)
                                found_accidental = True
                                break

                    if not found_accidental:
                        for j in range(i + 1, next_bound_idx):
                            acc = staff_symbols[j]
                            if acc["class_id"] in self.ACCIDENTALS:
                                if self._overlaps_1d(note_x_min, note_x_max, self._get_x_min(acc), self._get_x_max(acc)):
                                    note_event["modifiers"].append(
                                        {"type": "accidental", "value": self.ID_TO_NAME[acc["class_id"]]})
                                    attached_accidentals.append(acc)
                                    break

                    attached_dots = []
                    for j in range(i + 1, next_bound_idx):
                        dot = staff_symbols[j]
                        if dot["class_id"] == 13:
                            if self._overlaps_1d(note_y_min, note_y_max, self._get_y_min(dot), self._get_y_max(dot)):
                                if not any(m["type"] == "dot" for m in note_event["modifiers"]):
                                    note_event["modifiers"].append({"type": "dot"})
                                    attached_dots.append(dot)

                    for mod in staff_symbols:
                        mcid = mod["class_id"]
                        if mcid in [6, 14, 31]:
                            mod_x_min, mod_x_max = self._get_x_min(mod), self._get_x_max(mod)
                            x_overlap = self._overlaps_1d(note_x_min, note_x_max, mod_x_min, mod_x_max)

                            if mcid == 31:  # Tie/Slur
                                dot_overlap = any(
                                    self._overlaps_1d(self._get_x_min(d), self._get_x_max(d), mod_x_min, mod_x_max) for d in attached_dots)
                                acc_overlap = any(self._overlaps_1d(self._get_x_min(a), self._get_x_max(a), mod_x_min, mod_x_max) for a in
                                                  attached_accidentals)
                                if x_overlap or dot_overlap or acc_overlap:
                                    if not any(m["type"] == "slur" for m in note_event["modifiers"]):
                                        note_event["modifiers"].append({"type": "slur"})

                            elif mcid == 14:  # Fermata
                                if x_overlap:
                                    placement = "above" if self._get_y_center(mod) < self._get_y_center(sym) else "below"
                                    if not any(m["type"] == "fermata" for m in note_event["modifiers"]):
                                        note_event["modifiers"].append({"type": "fermata", "placement": placement})

                            elif mcid == 6:  # Cadence Point
                                if x_overlap:
                                    placement = "above" if self._get_y_center(mod) < self._get_y_center(sym) else "below"
                                    if not any(m["type"] == "cadence_point" for m in note_event["modifiers"]):
                                        note_event["modifiers"].append({"type": "cadence_point", "placement": placement})

                    current_measure_events.append(note_event)

                # ---------------------------------------------
                # RESTS
                # ---------------------------------------------
                elif cid in self.RESTS:
                    rest_event = {"type": "rest", "class_id": cid, "modifiers": []}

                    rest_x_min, rest_x_max = self._get_x_min(sym), self._get_x_max(sym)
                    rest_y_min, rest_y_max = self._get_y_min(sym), self._get_y_max(sym)

                    next_bound_idx = len(staff_symbols)
                    for j in range(i + 1, len(staff_symbols)):
                        if staff_symbols[j]["class_id"] in self.NOTES or staff_symbols[j]["class_id"] in self.RESTS or \
                                staff_symbols[j]["class_id"] in self.BARLINES:
                            next_bound_idx = j
                            break

                    for j in range(i + 1, next_bound_idx):
                        dot = staff_symbols[j]
                        if dot["class_id"] == 13:
                            if self._overlaps_1d(rest_y_min, rest_y_max, self._get_y_min(dot), self._get_y_max(dot)):
                                if not any(m["type"] == "dot" for m in rest_event["modifiers"]):
                                    rest_event["modifiers"].append({"type": "dot"})

                    for mod in staff_symbols:
                        mcid = mod["class_id"]
                        if mcid in [6, 14]:
                            if self._overlaps_1d(rest_x_min, rest_x_max, self._get_x_min(mod), self._get_x_max(mod)):
                                placement = "above" if self._get_y_center(mod) < self._get_y_center(sym) else "below"

                                if mcid == 14 and not any(m["type"] == "fermata" for m in rest_event["modifiers"]):
                                    rest_event["modifiers"].append({"type": "fermata", "placement": placement})

                                elif mcid == 6 and not any(m["type"] == "cadence_point" for m in rest_event["modifiers"]):
                                    rest_event["modifiers"].append({"type": "cadence_point", "placement": placement})

                    current_measure_events.append(rest_event)

        if current_measure_events:
            semantic_measures.append({
                "measure_number": global_measure_number,
                "right_barline": None,
                "page_id": current_measure_page,
                "staff_number": current_measure_staff,
                "events": current_measure_events
            })

        return {
            "voice_number": agnostic_data.get("voice_number", 1),
            "voice": agnostic_data.get("voice", "Voice 1"),
            "measures": semantic_measures
        }

    # --- 5. Semantic Generation Engine ---
    def process_partially_semantic_to_semantic(self, partially_semantic_data, cheatsheet, requires_coloration=False):
        # --- 0. Rhythm Resolution ---
        # Select the correct dictionary base based on global coloration check
        base_key = "base_12" if requires_coloration else "base_4"

        # In MusicXML, <divisions> is exactly equal to the ticks of one Quarter Note.
        divisions = int(cheatsheet["rhythm_divisions"][base_key]["note_quarter"]["duration"])

        # --- Global State Trackers ---
        active_clef = "clef_C4"
        active_key_sig = {}

        # XML Output Trackers (to prevent redundant printing)
        last_written_clef = None
        last_written_key_fifths = None

        # Track active time (default to 4/4) and ensure it prints in measure 1
        active_time = {"beats": 4, "beat_type": 4}
        time_signature_written = False

        # UNROLL TRACKERS
        output_measure_number = 1
        last_section_start_idx = 0

        fully_semantic = {
            "voice_number": partially_semantic_data.get("voice_number", 1),
            "voice": partially_semantic_data.get("voice", "Voice 1"),
            "divisions": divisions,
            "measures": []
        }

        for p_measure in partially_semantic_data.get("measures", []):
            f_measure = {
                "measure_number": output_measure_number,
                "events": []
            }

            if "page_id" in p_measure:
                f_measure["page_id"] = p_measure["page_id"]
            if "staff_number" in p_measure:
                f_measure["staff_number"] = p_measure["staff_number"]

            if p_measure.get("right_barline"):
                f_measure["right_barline"] = p_measure["right_barline"]

            measure_attributes = {}

            if not time_signature_written:
                measure_attributes["time_beats"] = active_time["beats"]
                measure_attributes["time_beat_type"] = active_time["beat_type"]
                time_signature_written = True

            for event in p_measure.get("events", []):

                # --- 1. CLEFS & KEY SIGNATURES ---
                if event["type"] == "clef":
                    active_clef = f"clef_{event['sign']}{event['line']}"

                    if active_clef != last_written_clef:
                        measure_attributes["clef_sign"] = event["sign"]
                        measure_attributes["clef_line"] = event["line"]
                        last_written_clef = active_clef

                    if "key_signature" in event:
                        active_key_sig = {}
                        unique_flats = set()
                        unique_sharps = set()

                        for acc in event["key_signature"]:
                            pos_key = f"{acc['position_type']}{acc['position_number']}"
                            val = -1 if acc["type"] == "flat" else 1 if acc["type"] == "sharp" else 0
                            active_key_sig[pos_key] = val

                            step = cheatsheet["clefs"].get(active_clef, {}).get(pos_key, {}).get("step")

                            if step:
                                if val == -1:
                                    unique_flats.add(step)
                                elif val == 1:
                                    unique_sharps.add(step)

                        fifths = len(unique_sharps) - len(unique_flats)

                        if fifths != last_written_key_fifths:
                            measure_attributes["key_fifths"] = fifths
                            last_written_key_fifths = fifths
                    elif active_key_sig:
                        active_key_sig = {}
                        if last_written_key_fifths != 0:
                            measure_attributes["key_fifths"] = 0
                            last_written_key_fifths = 0

                # --- 2. TIME SIGNATURES ---
                elif event["type"] == "time_signature":
                    val = event["value"]
                    if val == "time_C":
                        active_time = {"beats": 4, "beat_type": 4}
                    elif val == "time_cut":
                        active_time = {"beats": 2, "beat_type": 2}
                    elif val.startswith("digit_"):
                        digit = int(val.split("_")[1])
                        active_time = {"beats": digit, "beat_type": 2}

                    measure_attributes["time_beats"] = active_time["beats"]
                    measure_attributes["time_beat_type"] = active_time["beat_type"]
                    time_signature_written = True

                # --- 3. NOTES & RESTS ---
                elif event["type"] in ["note", "rest"]:
                    cid = event["class_id"]
                    rhythm_key = self.ID_TO_RHYTHM.get(cid, "note_quarter")

                    rhythm_data = cheatsheet["rhythm_divisions"][base_key].get(rhythm_key,
                                                                               {"duration": 1, "xml_type": "quarter"})

                    duration_ticks = float(rhythm_data["duration"])

                    f_event = {
                        "type": event["type"],
                        "note_type": rhythm_data["xml_type"]
                    }

                    mods = event.get("modifiers", [])
                    mod_types = [m["type"] for m in mods]

                    if "dot" in mod_types:
                        duration_ticks *= 1.5
                        f_event["has_dot"] = True
                    if cid == 22:
                        duration_ticks *= 0.666667
                        f_event["is_colored"] = True

                    f_event["duration_ticks"] = round(duration_ticks)

                    if event["type"] == "note":
                        pos_key = f"{event['position_type']}{event['position_number']}"

                        pitch_data = cheatsheet["clefs"].get(active_clef, {}).get(pos_key, {"step": "C", "octave": 4})
                        f_event["pitch_step"] = pitch_data["step"]
                        f_event["pitch_octave"] = pitch_data["octave"]

                        current_alter = active_key_sig.get(pos_key, 0)
                        visual_ink = None

                        for m in mods:
                            if m["type"] == "accidental":
                                visual_ink = m["value"]
                                if m["value"] == "flat":
                                    current_alter = -1
                                elif m["value"] == "sharp":
                                    current_alter = 1
                                elif m["value"] == "natural":
                                    current_alter = 0

                        f_event["alter"] = current_alter
                        if visual_ink:
                            f_event["visual_accidental"] = visual_ink

                    if "slur" in mod_types:
                        f_event["has_slur"] = True
                    for m in mods:
                        if m["type"] in ["fermata", "cadence_point"]:
                            f_event[m["type"]] = m.get("placement", "above")

                    f_measure["events"].append(f_event)

            if measure_attributes:
                measure_attributes["type"] = "attributes"
                f_measure["events"].insert(0, measure_attributes)

            # --- REPEAT DATA UNROLL LOGIC ---
            is_repeat = (f_measure.get("right_barline") == "repeat")
            is_double = (f_measure.get("right_barline") == "barline_double")

            if is_repeat:
                f_measure["right_barline"] = "barline"

            fully_semantic["measures"].append(f_measure)
            output_measure_number += 1

            if is_repeat:
                section_to_duplicate = fully_semantic["measures"][
                                       last_section_start_idx: len(fully_semantic["measures"])]

                for orig_measure in section_to_duplicate:
                    dup_measure = copy.deepcopy(orig_measure)
                    dup_measure["measure_number"] = output_measure_number
                    dup_measure["is_repeated_unroll"] = True

                    fully_semantic["measures"].append(dup_measure)
                    output_measure_number += 1

                last_section_start_idx = len(fully_semantic["measures"])

            elif is_double:
                last_section_start_idx = len(fully_semantic["measures"])

        return fully_semantic

    # --- 6. Synchronization & Export Engine ---
    @staticmethod
    def _get_measure_ticks(measure):
        """Calculates the total duration ticks of all notes/rests in a measure."""
        return sum(e.get("duration_ticks", 0) for e in measure["events"] if e["type"] in ["note", "rest"])

    @staticmethod
    def _get_splitable_event_count(measure):
        """Counts how many notes/rests exist (we need at least 2 to split a measure)."""
        return len([e for e in measure["events"] if e["type"] in ["note", "rest"]])

    def sync_voices(self, voices_data):
        # 1. Gather all unique page_ids across the entire score
        page_ids = set()
        for voice in voices_data:
            for m in voice["measures"]:
                if "page_id" in m:
                    page_ids.add(m["page_id"])

        sorted_pages = sorted(list(page_ids))

        # 2. Iterate through each physical page in the book
        for p_id in sorted_pages:
            # Find the Anchor Count (the maximum number of measures any voice has on this page)
            anchor_count = 0
            for voice in voices_data:
                count = sum(1 for m in voice["measures"] if m.get("page_id") == p_id)
                if count > anchor_count:
                    anchor_count = count

            if anchor_count == 0:
                continue

            # 3. Synchronize every voice to match the Anchor Count
            for voice_idx, voice in enumerate(voices_data):
                while True:
                    # Count current measures on this page for this specific voice
                    current_count = sum(1 for m in voice["measures"] if m.get("page_id") == p_id)

                    if current_count >= anchor_count:
                        break  # This voice is synchronized for this page!

                    # Find the longest measure on this page
                    max_ticks = -1
                    target_global_idx = -1

                    for global_idx, m in enumerate(voice["measures"]):
                        if m.get("page_id") == p_id:
                            ticks = self._get_measure_ticks(m)
                            splitable = self._get_splitable_event_count(m)
                            # We can only split if there are at least 2 events
                            if ticks > max_ticks and splitable >= 2:
                                max_ticks = ticks
                                target_global_idx = global_idx

                    # Safety Net: What if a voice has a page with missing notes, so we can't split?
                    if target_global_idx == -1:
                        # We inject a blank "rest" measure to pad the count
                        insert_idx = -1
                        last_num = 1
                        for idx, m in enumerate(voice["measures"]):
                            if m.get("page_id") == p_id:
                                insert_idx = idx
                                last_num = m["measure_number"]

                        if insert_idx != -1:
                            empty_measure = {
                                "measure_number": last_num + 1,
                                "page_id": p_id,
                                "events": [{"type": "rest", "note_type": "whole",
                                            "duration_ticks": voice.get("divisions", 12) * 4}],
                                "right_barline": "barline"
                            }
                            if "staff_number" in voice["measures"][insert_idx]:
                                empty_measure["staff_number"] = voice["measures"][insert_idx]["staff_number"]

                            voice["measures"].insert(insert_idx + 1, empty_measure)
                            for i in range(insert_idx + 2, len(voice["measures"])):
                                voice["measures"][i]["measure_number"] += 1
                        break

                    # --- THE MIDPOINT SLICE ---
                    m_to_split = voice["measures"][target_global_idx]
                    midpoint = max_ticks / 2.0

                    running_ticks = 0
                    slice_idx = len(m_to_split["events"]) - 1  # Safe fallback

                    # Find exact slice point
                    for idx, e in enumerate(m_to_split["events"]):
                        if e["type"] in ["note", "rest"]:
                            running_ticks += e.get("duration_ticks", 0)
                            if running_ticks >= midpoint:
                                # Slice immediately after this note
                                if idx + 1 < len(m_to_split["events"]):
                                    slice_idx = idx + 1
                                break

                    # Create Measure A and Measure B
                    measure_A = copy.deepcopy(m_to_split)
                    measure_B = {
                        "measure_number": m_to_split["measure_number"] + 1,
                        "events": []
                    }

                    # Copy page/staff metadata
                    for key in ["page_id", "staff_number"]:
                        if key in m_to_split:
                            measure_B[key] = m_to_split[key]

                    # Distribute events based on our slice
                    measure_A["events"] = m_to_split["events"][:slice_idx]
                    measure_B["events"] = m_to_split["events"][slice_idx:]

                    # Manage the barlines
                    measure_B["right_barline"] = m_to_split.get("right_barline", "barline")
                    measure_A["right_barline"] = "barline"  # Normal barline for the artificial split
                    measure_A["is_artificial_split"] = True  # Add flag in case we want to debug later

                    # Apply the slice to the main array
                    voice["measures"][target_global_idx] = measure_A
                    voice["measures"].insert(target_global_idx + 1, measure_B)

                    # --- THE RIPPLE EFFECT ---
                    # Push every subsequent measure down by 1
                    for i in range(target_global_idx + 2, len(voice["measures"])):
                        voice["measures"][i]["measure_number"] += 1

        return voices_data

    def generate_musicxml(self, all_voices_data, cheatsheet, output_filename, project_name=None):
        lines = []

        def add(text, indent=0):
            lines.append("  " * indent + text)

        def extract_inner_notation(tag_string):
            return tag_string.replace("<notations>", "").replace("</notations>", "")

        # --- 1. XML Header and Document Start ---
        add('<?xml version="1.0" encoding="UTF-8"?>')
        add('<!DOCTYPE score-partwise PUBLIC "-//Recordare//DTD MusicXML 3.1 Partwise//EN" "http://www.musicxml.org/dtds/partwise.dtd">')
        add('<score-partwise version="3.1">')
        
        if project_name:
            add('<work>', 1)
            add(f'<work-title>{html.escape(project_name)}</work-title>', 2)
            add('</work>', 1)

        add('<part-list>', 1)

        is_multi_voice = len(all_voices_data) > 1

        if is_multi_voice:
            add('<part-group type="start" number="1">', 2)
            add('<group-symbol>bracket</group-symbol>', 3)
            add('<group-barline>yes</group-barline>', 3)
            add('</part-group>', 2)

        for voice_data in all_voices_data:
            v_num = voice_data.get("voice_number", 1)
            v_name = html.escape(voice_data.get("voice", f"Voice {v_num}"))
            add(f'<score-part id="P{v_num}">', 2)
            add(f'<part-name>{v_name}</part-name>', 3)
            add('</score-part>', 2)

        if is_multi_voice:
            add('<part-group type="stop" number="1"/>', 2)

        add('</part-list>', 1)

        # --- 2. ITERATE VOICES ---
        for voice_data in all_voices_data:
            v_num = voice_data.get("voice_number", 1)
            divisions = voice_data.get("divisions", 4)
            first_measure = True

            add(f'<part id="P{v_num}">', 1)

            all_notes = []
            for measure in voice_data["measures"]:
                for event in measure["events"]:
                    if event["type"] in ["note", "rest"]:
                        all_notes.append(event)

            for i, note in enumerate(all_notes):
                if note.get("has_slur", False):
                    prev_has_slur = all_notes[i - 1].get("has_slur", False) if i > 0 else False
                    next_has_slur = all_notes[i + 1].get("has_slur", False) if i < len(all_notes) - 1 else False
                    note["slur_start"] = not prev_has_slur
                    note["slur_stop"] = not next_has_slur

            for measure in voice_data["measures"]:
                measure_num = measure["measure_number"]
                add(f'<measure number="{measure_num}">', 2)

                if "page_id" in measure and "staff_number" in measure:
                    repeat_text = " - repeated" if measure.get("is_repeated_unroll") else ""
                    add('<direction placement="above" system="only-top">', 3)
                    add('<direction-type>', 4)
                    add(f'<words font-weight="bold" font-size="10">p{measure["page_id"]}, s{measure["staff_number"] + 1}{repeat_text}</words>', 5)
                    add('</direction-type>', 4)
                    add('</direction>', 3)

                if measure.get("left_barline") == "repeat_start":
                    add('<barline location="left">', 3)
                    add('<bar-style>heavy-light</bar-style>', 4)
                    add('<repeat direction="forward"/>', 4)
                    add('</barline>', 3)

                for event in measure["events"]:
                    if event["type"] == "attributes":
                        add('<attributes>', 3)
                        if first_measure:
                            add(f'<divisions>{divisions}</divisions>', 4)
                            first_measure = False
                        if "key_fifths" in event:
                            add('<key>', 4)
                            add(f'<fifths>{event["key_fifths"]}</fifths>', 5)
                            add('</key>', 4)
                        if "time_beats" in event and "time_beat_type" in event:
                            add('<time>', 4)
                            add(f'<beats>{event["time_beats"]}</beats>', 5)
                            add(f'<beat-type>{event["time_beat_type"]}</beat-type>', 5)
                            add('</time>', 4)
                        if "clef_sign" in event and "clef_line" in event:
                            add('<clef>', 4)
                            add(f'<sign>{event["clef_sign"]}</sign>', 5)
                            add(f'<line>{event["clef_line"]}</line>', 5)
                            add('</clef>', 4)
                        add('</attributes>', 3)

                    elif event["type"] in ["note", "rest"]:
                        add('<note>', 3)
                        if event["type"] == "rest":
                            add('<rest/>', 4)
                        else:
                            add('<pitch>', 4)
                            add(f'<step>{event["pitch_step"]}</step>', 5)
                            if event.get("alter", 0) != 0:
                                add(f'<alter>{event["alter"]}</alter>', 5)
                            add(f'<octave>{event["pitch_octave"]}</octave>', 5)
                            add('</pitch>', 4)

                        add(f'<duration>{event["duration_ticks"]}</duration>', 4)
                        add(f'<type>{event["note_type"]}</type>', 4)

                        if event.get("has_dot"):
                            add('<dot/>', 4)
                        if "visual_accidental" in event:
                            add(f'<accidental>{event["visual_accidental"]}</accidental>', 4)
                        if event.get("is_colored"):
                            tag = cheatsheet["modifiers"]["coloration"]["xml_tag"]
                            add(tag, 4)

                        notations = []
                        if event.get("slur_start"): notations.append('<slur type="start" number="1"/>')
                        if event.get("slur_stop"): notations.append('<slur type="stop" number="1"/>')
                        if "fermata" in event:
                            notations.append(extract_inner_notation(cheatsheet["modifiers"]["fermata"]["xml_tag"]))
                        if "cadence_point" in event:
                            key = f"signum_congruentiae_{event['cadence_point']}"
                            if key in cheatsheet["modifiers"]:
                                notations.append(extract_inner_notation(cheatsheet["modifiers"][key]["xml_tag"]))

                        if notations:
                            add('<notations>', 4)
                            for n in notations: add(n, 5)
                            add('</notations>', 4)
                        add('</note>', 3)

                rb = measure.get("right_barline")
                if rb == "barline_double":
                    add('<barline location="right">', 3)
                    add('<bar-style>light-light</bar-style>', 4)
                    add('</barline>', 3)
                elif rb == "repeat":
                    add('<barline location="right">', 3)
                    add('<bar-style>light-heavy</bar-style>', 4)
                    add('<repeat direction="backward"/>', 4)
                    add('</barline>', 3)

                add('</measure>', 2)
            add('</part>', 1)

        # --- 3. Close Document ---
        add('</score-partwise>')

        with open(output_filename, 'w', encoding='utf-8') as f:
            f.write("\n".join(lines))

    def generate_duration_validation(self, voices_data, output_file):
        if not voices_data:
            print("No voice data provided for validation.")
            return

        divisions = voices_data[0].get("divisions", 12)
        num_measures = len(voices_data[0].get("measures", []))
        
        voice_names = []
        for i, voice in enumerate(voices_data):
            v_name = voice.get("voice", f"Voice {voice.get('voice_number', i + 1)}")
            voice_names.append(v_name)

        report = {
            "divisions": divisions,
            "voices": voice_names,
            "measures": []
        }

        for i in range(num_measures):
            measure_num = voices_data[0]["measures"][i].get("measure_number", i + 1)
            durations = []
            locations = []

            for voice in voices_data:
                if i < len(voice["measures"]):
                    measure = voice["measures"][i]
                    durations.append(self._get_measure_ticks(measure))
                    locations.append({
                        "page_id": measure.get("page_id"),
                        "staff_number": measure.get("staff_number")
                    })
                else:
                    durations.append(0)
                    locations.append({"page_id": None, "staff_number": None})

            is_equal = len(set(durations)) <= 1

            report["measures"].append({
                "measure_number": measure_num,
                "is_equal": is_equal,
                "durations": durations,
                "locations": locations
            })

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2)
