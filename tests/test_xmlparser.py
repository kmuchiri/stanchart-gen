"""
Unit and integration tests for xmlparser.py
"""

from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

import xmlparser


SAMPLE_PARTICIPANT_XML = """
<content>
    <overallPosition>1</overallPosition>
    <name>Test Runner</name>
    <country>KE</country>
    <genderPosition>1</genderPosition>
    <gender>M</gender>
    <bib>1001</bib>
    <gunTimeOfParticipant>02:10:00.000</gunTimeOfParticipant>
    <chipTimeOfParticipant>02:09:50.000</chipTimeOfParticipant>
    <legs>
        <legs>
            <legDuration>02:09:50</legDuration>
            <participantSplits>
                <participantSplits>
                    <distanceInMeters>10000</distanceInMeters>
                    <splitDuration>00:29:30</splitDuration>
                    <totalSplitDuration>00:29:30</totalSplitDuration>
                    <splitName>10.0 km</splitName>
                    <personalSplitSpeed>20.33</personalSplitSpeed>
                </participantSplits>
                <participantSplits>
                    <distanceInMeters>21100</distanceInMeters>
                    <splitDuration>00:32:00</splitDuration>
                    <totalSplitDuration>01:01:30</totalSplitDuration>
                    <splitName>21.1 km</splitName>
                    <personalSplitSpeed>20.81</personalSplitSpeed>
                </participantSplits>
            </participantSplits>
        </legs>
    </legs>
</content>
"""

SAMPLE_PARTICIPANT_NO_SPLITS_XML = """
<content>
    <overallPosition>99</overallPosition>
    <name>Runner Without Splits</name>
    <country>UG</country>
    <genderPosition>80</genderPosition>
    <gender>F</gender>
    <bib>2002</bib>
    <gunTimeOfParticipant>03:00:00.000</gunTimeOfParticipant>
    <chipTimeOfParticipant>02:59:00.000</chipTimeOfParticipant>
</content>
"""


class TestXMLParser(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.output_dir = Path(self.temp_dir.name) / "output"
        self.xml_dir = Path(self.temp_dir.name) / "xml"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.xml_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_natural_sort_key(self):
        files = ["page_10.xml", "page_1.xml", "page_2.xml", "page_20.xml"]
        sorted_files = sorted(files, key=xmlparser.natural_sort_key)
        self.assertEqual(sorted_files, ["page_1.xml", "page_2.xml", "page_10.xml", "page_20.xml"])

    def test_sort_participants_by_position(self):
        participants = [
            {"overall_position": "10", "competitor_name": "Ten"},
            {"overall_position": "2", "competitor_name": "Two"},
            {"overall_position": "1", "competitor_name": "One"},
            {"overall_position": "", "competitor_name": "Unknown"},
        ]
        sorted_p = xmlparser.sort_participants_by_position(participants)
        names = [p["competitor_name"] for p in sorted_p]
        self.assertEqual(names, ["One", "Two", "Ten", "Unknown"])

    def test_clean_split_column_name(self):
        self.assertEqual(xmlparser._clean_split_column_name("7.4 km"), "7_4km")
        self.assertEqual(xmlparser._clean_split_column_name("42.195 km"), "42_195km")
        self.assertEqual(xmlparser._clean_split_column_name("", "5000"), "5000m")
        self.assertEqual(xmlparser._clean_split_column_name("", ""), "unknown")

    def test_parse_participant_full(self):
        elem = ET.fromstring(SAMPLE_PARTICIPANT_XML)
        p = xmlparser.parse_participant(elem, event_name="full-marathon")

        self.assertEqual(p["overall_position"], "1")
        self.assertEqual(p["competitor_name"], "Test Runner")
        self.assertEqual(p["country"], "KE")
        self.assertEqual(p["gender_position"], "1")
        self.assertEqual(p["gender"], "M")
        self.assertEqual(p["bib"], "1001")
        self.assertEqual(p["event_name"], "full-marathon")
        self.assertEqual(p["gun_time"], "02:10:00.000")
        self.assertEqual(p["bib_time"], "02:09:50.000")
        self.assertEqual(len(p["splits"]), 2)

        s1 = p["splits"][0]
        self.assertEqual(s1["split_name"], "10.0 km")
        self.assertEqual(s1["distance_in_meters"], "10000")
        self.assertEqual(s1["split_duration"], "00:29:30")
        self.assertEqual(s1["total_split_duration"], "00:29:30")
        self.assertEqual(s1["personal_split_speed"], "20.33")

    def test_parse_participant_missing_splits(self):
        elem = ET.fromstring(SAMPLE_PARTICIPANT_NO_SPLITS_XML)
        p = xmlparser.parse_participant(elem, event_name="10K")

        self.assertEqual(p["competitor_name"], "Runner Without Splits")
        self.assertEqual(p["splits"], [])

    def test_participants_to_split_rows(self):
        elem1 = ET.fromstring(SAMPLE_PARTICIPANT_XML)
        elem2 = ET.fromstring(SAMPLE_PARTICIPANT_NO_SPLITS_XML)
        p1 = xmlparser.parse_participant(elem1, event_name="full-marathon")
        p2 = xmlparser.parse_participant(elem2, event_name="10K")

        rows = xmlparser.participants_to_split_rows([p1, p2])
        # p1 has 2 splits -> 2 rows, p2 has 0 splits -> 1 row with empty split fields
        self.assertEqual(len(rows), 3)

        self.assertEqual(rows[0]["competitor_name"], "Test Runner")
        self.assertEqual(rows[0]["split_name"], "10.0 km")
        self.assertEqual(rows[0]["split_time"], "00:29:30")
        self.assertEqual(rows[0]["split_speed"], "20.33")

        self.assertEqual(rows[1]["competitor_name"], "Test Runner")
        self.assertEqual(rows[1]["split_name"], "21.1 km")

        self.assertEqual(rows[2]["competitor_name"], "Runner Without Splits")
        self.assertEqual(rows[2]["split_name"], "")
        self.assertEqual(rows[2]["split_speed"], "")

    def test_participants_to_wide_rows(self):
        elem = ET.fromstring(SAMPLE_PARTICIPANT_XML)
        p = xmlparser.parse_participant(elem, event_name="full-marathon")

        rows, fieldnames = xmlparser.participants_to_wide_rows([p])
        self.assertEqual(len(rows), 1)

        self.assertIn("split_10_0km_time", fieldnames)
        self.assertIn("split_10_0km_speed", fieldnames)
        self.assertIn("split_21_1km_time", fieldnames)
        self.assertIn("split_21_1km_speed", fieldnames)

        row = rows[0]
        self.assertEqual(row["competitor_name"], "Test Runner")
        self.assertEqual(row["split_10_0km_time"], "00:29:30")
        self.assertEqual(row["split_10_0km_speed"], "20.33")
        self.assertEqual(row["split_21_1km_time"], "00:32:00")
        self.assertEqual(row["split_21_1km_speed"], "20.81")

    def test_parse_xml_file_and_export(self):
        event_dir = self.xml_dir / "half-marathon"
        event_dir.mkdir(parents=True)
        xml_file = event_dir / "page_0.xml"

        xml_content = f"""<PagedResponse>
            <content>
                {SAMPLE_PARTICIPANT_XML}
                {SAMPLE_PARTICIPANT_NO_SPLITS_XML}
            </content>
        </PagedResponse>"""
        xml_file.write_text(xml_content, encoding="utf-8")

        participants = xmlparser.parse_xml_file(xml_file)
        self.assertEqual(len(participants), 2)

        created = xmlparser.export_event_csv(
            participants=participants,
            event_name="half-marathon",
            output_dir=self.output_dir,
            output_format="both",
        )
        self.assertIn("split", created)
        self.assertIn("wide", created)
        self.assertTrue(created["split"].is_file())
        self.assertTrue(created["wide"].is_file())

    def test_parse_invalid_xml(self):
        bad_xml = self.xml_dir / "corrupted.xml"
        bad_xml.write_text("<PagedResponse><content>unclosed tag", encoding="utf-8")

        participants = xmlparser.parse_xml_file(bad_xml)
        self.assertEqual(participants, [])


if __name__ == "__main__":
    unittest.main()
