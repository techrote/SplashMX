import unittest
from projection import LEVELS,SURFACES,semantic_union,visible_text

FORBIDDEN=("Node","SceneTree","Resource","NodePath","RID","GDScript","RPC","WebRTC","WebSocket","ENet","Godot","package manager","compiler","build system")

class ProjectionTests(unittest.TestCase):
    def test_disclosure_is_monotonic(self):
        prior=frozenset()
        for level in LEVELS:
            current=semantic_union(level)
            self.assertTrue(prior<=current)
            prior=current
    def test_author_text_has_no_engine_or_build_terms(self):
        for level in LEVELS:
            text=" ".join(visible_text(level)).lower()
            for forbidden in FORBIDDEN:
                self.assertNotIn(forbidden.lower(),text)
    def test_surface_purposes_are_author_facing(self):
        for surface in SURFACES.values():
            self.assertTrue(surface.purpose)
            self.assertTrue(surface.semantics)
    def test_timeline_not_mandatory_at_canvas_level(self):
        self.assertNotIn("Timeline",visible_text("canvas"))
    def test_simple_multiplayer_words_appear_without_transport_words(self):
        text=" ".join(visible_text("together"))
        self.assertIn("One per player",text)
        self.assertIn("Shared",text)
    def test_advanced_reveals_real_splashmx_relationship_axes(self):
        text=visible_text("advanced")
        for term in ("Control","Authority","Replication","Relevance"):
            self.assertIn(term,text)

if __name__=="__main__": unittest.main()
