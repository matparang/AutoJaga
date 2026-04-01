"""
Enhanced KnowledgeGraph — Entity and relation extraction.

Adds NLP-powered entity extraction and relationship discovery to KnowledgeGraph.
Gracefully falls back to keyword extraction if spacy not installed.

Usage:
    from jagabot.memory.knowledge_graph_enhanced import EnhancedKnowledgeGraph
    
    graph = EnhancedKnowledgeGraph(workspace=Path.home() / ".jagabot" / "workspace")
    entities = graph.extract_entities("Apple stock rose 5% on strong earnings")
    relations = graph.extract_relations("Investors bought shares after the report")
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

from loguru import logger

# Try to import spacy, fall back to regex extraction if not available
try:
    import spacy
    SPACY_SUPPORT = True
except ImportError:
    SPACY_SUPPORT = False
    logger.warning("spacy not installed. EnhancedKnowledgeGraph will use keyword extraction only.")
    logger.warning("Install with: pip install spacy && python -m spacy download en_core_web_sm")


class EnhancedKnowledgeGraph:
    """
    Enhanced KnowledgeGraph with entity and relation extraction.
    
    Extends basic KnowledgeGraph with NLP capabilities for:
    - Named entity recognition (organizations, people, dates, etc.)
    - Subject-verb-object relation extraction
    - Entity graph construction
    """
    
    def __init__(self, workspace: Path | str | None = None):
        self.workspace = Path(workspace) if workspace else Path.home() / ".jagabot" / "workspace"
        self.memory_dir = self.workspace / "memory"
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize NLP if available
        if SPACY_SUPPORT:
            try:
                self.nlp = spacy.load("en_core_web_sm")
                logger.info("EnhancedKnowledgeGraph: loaded spacy model")
            except OSError:
                logger.warning("EnhancedKnowledgeGraph: spacy model not found. Run: python -m spacy download en_core_web_sm")
                self.nlp = None
        else:
            self.nlp = None
        
        # Entity and relation storage
        self.entities: Dict[str, Set[str]] = defaultdict(set)
        self.relations: List[Dict[str, str]] = []
        self.entity_graph: Dict[str, Set[str]] = defaultdict(set)
        
        # Output file
        self.graph_file = self.memory_dir / "entity_graph.json"
        self._load_graph()
    
    def _load_graph(self):
        """Load existing graph from disk."""
        if not self.graph_file.exists():
            return
        
        try:
            data = json.loads(self.graph_file.read_text())
            for entity_type, items in data.get("entities", {}).items():
                self.entities[entity_type].update(items)
            self.relations = data.get("relations", [])
            for subject, objects in data.get("graph", {}).items():
                self.entity_graph[subject].update(objects)
            logger.debug(f"EnhancedKnowledgeGraph: loaded {len(self.entities)} entity types")
        except Exception as e:
            logger.warning(f"EnhancedKnowledgeGraph: failed to load graph: {e}")
    
    def _save_graph(self):
        """Persist graph to disk."""
        try:
            data = {
                "entities": {k: list(v) for k, v in self.entities.items()},
                "relations": self.relations,
                "graph": {k: list(v) for k, v in self.entity_graph.items()},
                "updated_at": datetime.now().isoformat()
            }
            self.graph_file.write_text(json.dumps(data, indent=2))
            logger.debug("EnhancedKnowledgeGraph: saved graph")
        except Exception as e:
            logger.warning(f"EnhancedKnowledgeGraph: failed to save graph: {e}")
    
    def extract_entities(self, text: str) -> Dict[str, List[str]]:
        """
        Extract named entities from text.
        
        Args:
            text: Input text
        
        Returns:
            Dict mapping entity types to lists of entities
        """
        if self.nlp is not None:
            return self._spacy_extract_entities(text)
        else:
            return self._keyword_extract_entities(text)
    
    def _spacy_extract_entities(self, text: str) -> Dict[str, List[str]]:
        """Extract entities using spacy NER."""
        doc = self.nlp(text)
        extracted = defaultdict(list)
        
        for ent in doc.ents:
            entity_type = ent.label_
            entity_text = ent.text
            extracted[entity_type].append(entity_text)
            self.entities[entity_type].add(entity_text)
        
        self._save_graph()
        return dict(extracted)
    
    def _keyword_extract_entities(self, text: str) -> Dict[str, List[str]]:
        """Fallback keyword-based entity extraction."""
        extracted = defaultdict(list)
        
        # Pattern-based extraction
        patterns = {
            "MONEY": r'\$[\d,]+(?:\.\d+)?(?:\s*(?:million|billion|trillion))?',
            "PERCENT": r'\d+(?:\.\d+)?%',
            "DATE": r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2},? \d{4}\b',
            "ORG_CAPS": r'\b[A-Z]{2,}(?:\s+[A-Z]{2,})*\b',
        }
        
        for entity_type, pattern in patterns.items():
            matches = re.findall(pattern, text)
            for match in matches:
                extracted[entity_type].append(match)
                self.entities[entity_type].add(match)
        
        self._save_graph()
        return dict(extracted)
    
    def extract_relations(self, text: str) -> List[Dict[str, str]]:
        """
        Extract subject-verb-object relations from text.
        
        Args:
            text: Input text
        
        Returns:
            List of relation dicts with subject, verb, object
        """
        if self.nlp is not None:
            return self._spacy_extract_relations(text)
        else:
            return self._keyword_extract_relations(text)
    
    def _spacy_extract_relations(self, text: str) -> List[Dict[str, str]]:
        """Extract relations using spacy dependency parsing."""
        doc = self.nlp(text)
        relations = []
        
        for token in doc:
            # Look for verb roots
            if token.dep_ == "ROOT" and token.pos_ in ("VERB", "AUX"):
                # Find subjects
                subjects = [w for w in token.lefts if w.dep_ in ("nsubj", "nsubjpass")]
                # Find objects
                objects = [w for w in token.rights if w.dep_ in ("dobj", "attr", "pobj")]
                
                if subjects and objects:
                    relation = {
                        "subject": subjects[0].text,
                        "verb": token.text,
                        "object": objects[0].text,
                        "sentence": token.sent.text.strip()
                    }
                    relations.append(relation)
                    self.relations.append(relation)
                    
                    # Build entity graph
                    self.entity_graph[subjects[0].text].add(objects[0].text)
        
        self._save_graph()
        return relations
    
    def _keyword_extract_relations(self, text: str) -> List[Dict[str, str]]:
        """Fallback keyword-based relation extraction."""
        relations = []
        
        # Simple pattern: "X verb Y"
        patterns = [
            (r'(\w+)\s+(rose|fell|increased|decreased|bought|sold|hit|reached)\s+(\w+)', 2, 1, 3),
            (r'(\w+)\s+(is|was|are|were)\s+(\w+)', 1, 2, 3),
        ]
        
        for pattern, verb_grp, subj_grp, obj_grp in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                relation = {
                    "subject": match[subj_grp - 1],
                    "verb": match[verb_grp - 1],
                    "object": match[obj_grp - 1],
                    "sentence": text.strip()
                }
                relations.append(relation)
                self.relations.append(relation)
                self.entity_graph[relation["subject"]].add(relation["object"])
        
        self._save_graph()
        return relations
    
    def analyze_text(self, text: str) -> Dict[str, Any]:
        """
        Full NLP analysis of text.
        
        Args:
            text: Input text
        
        Returns:
            Comprehensive analysis dict
        """
        entities = self.extract_entities(text)
        relations = self.extract_relations(text)
        
        return {
            "entities": entities,
            "relations": relations,
            "entity_count": sum(len(v) for v in entities.values()),
            "relation_count": len(relations),
            "connected_entities": len(self.entity_graph),
            "entity_types": list(entities.keys())
        }
    
    def get_entity_connections(self, entity: str) -> List[str]:
        """
        Get all entities connected to given entity.
        
        Args:
            entity: Source entity
        
        Returns:
            List of connected entities
        """
        return list(self.entity_graph.get(entity, []))
    
    def get_stats(self) -> Dict[str, Any]:
        """Return graph statistics."""
        return {
            "total_entity_types": len(self.entities),
            "total_entities": sum(len(v) for v in self.entities.values()),
            "total_relations": len(self.relations),
            "connected_entities": len(self.entity_graph),
            "spacy_support": SPACY_SUPPORT,
            "nlp_loaded": self.nlp is not None
        }
    
    def query_entities(self, entity_type: str | None = None) -> Dict[str, List[str]]:
        """
        Query stored entities by type.
        
        Args:
            entity_type: Optional entity type filter
        
        Returns:
            Dict of entity types to entities
        """
        if entity_type:
            return {entity_type: list(self.entities.get(entity_type, []))}
        return {k: list(v) for k, v in self.entities.items()}
    
    def find_entity_paths(self, source: str, target: str, max_depth: int = 3) -> List[List[str]]:
        """
        Find paths between two entities in the graph.
        
        Args:
            source: Source entity
            target: Target entity
            max_depth: Maximum path length
        
        Returns:
            List of paths (each path is a list of entities)
        """
        paths = []
        
        def dfs(current: str, path: List[str], depth: int):
            if depth > max_depth:
                return
            if current == target and len(path) > 1:
                paths.append(path[:])
                return
            
            for neighbor in self.entity_graph.get(current, []):
                if neighbor not in path:
                    dfs(neighbor, path + [neighbor], depth + 1)
        
        dfs(source, [source], 0)
        return paths
    
    def export_graph(self, output_file: str | None = None) -> Path:
        """
        Export entity-relation graph to JSON.
        
        Args:
            output_file: Optional output filename
        
        Returns:
            Path to exported file
        """
        output_path = self.workspace / (output_file or "entity_graph.json")
        
        data = {
            "entities": {k: list(v) for k, v in self.entities.items()},
            "relations": self.relations,
            "graph": {k: list(v) for k, v in self.entity_graph.items()},
            "stats": self.get_stats(),
            "exported_at": datetime.now().isoformat()
        }
        
        output_path.write_text(json.dumps(data, indent=2))
        return output_path
    
    def clear(self):
        """Clear all entities and relations."""
        self.entities.clear()
        self.relations.clear()
        self.entity_graph.clear()
        self._save_graph()


class EnhancedKnowledgeGraphTool:
    """
    Tool wrapper for EnhancedKnowledgeGraph.
    Can be used as a jagabot tool for entity/relation operations.
    """
    
    def __init__(self, workspace: Path | str | None = None):
        self.graph = EnhancedKnowledgeGraph(workspace)
    
    async def execute(self, action: str, **kwargs) -> str:
        """
        Execute knowledge graph action.
        
        Args:
            action: One of: analyze, entities, relations, stats, query, paths, export
            **kwargs: Action-specific parameters
        
        Returns:
            JSON string result
        """
        import json
        
        if action == "analyze":
            text = kwargs.get("text", "")
            result = self.graph.analyze_text(text)
            return json.dumps(result)
        
        elif action == "entities":
            entity_type = kwargs.get("type")
            result = self.graph.query_entities(entity_type)
            return json.dumps(result)
        
        elif action == "relations":
            text = kwargs.get("text", "")
            if text:
                result = self.graph.extract_relations(text)
            else:
                result = self.graph.relations[-20:]  # Last 20 relations
            return json.dumps({"relations": result, "count": len(result)})
        
        elif action == "stats":
            result = self.graph.get_stats()
            return json.dumps(result)
        
        elif action == "query":
            entity = kwargs.get("entity", "")
            result = self.graph.get_entity_connections(entity)
            return json.dumps({
                "entity": entity,
                "connections": result,
                "count": len(result)
            })
        
        elif action == "paths":
            source = kwargs.get("source", "")
            target = kwargs.get("target", "")
            max_depth = kwargs.get("max_depth", 3)
            result = self.graph.find_entity_paths(source, target, max_depth)
            return json.dumps({
                "source": source,
                "target": target,
                "paths": result,
                "count": len(result)
            })
        
        elif action == "export":
            output_file = kwargs.get("output_file")
            path = self.graph.export_graph(output_file)
            return json.dumps({
                "exported": str(path),
                "stats": self.graph.get_stats()
            })
        
        else:
            return json.dumps({"error": f"Unknown action: {action}"})
