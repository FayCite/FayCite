import json
import os
import re
from typing import Dict, List, Any, Optional, Tuple
from openai import AzureOpenAI
import nltk
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from enum import Enum

# Download required NLTK data
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')

class ClaimType(Enum):
    """Enumeration of academic claim types for targeted citation strategies."""
    FACTUAL = "factual"  # Require authoritative sources
    STATISTICAL = "statistical"  # Require data sources with methodology
    THEORETICAL = "theoretical"  # Require foundational academic sources
    METHODOLOGICAL = "methodological"  # Require peer-reviewed research methods
    OPINION_INTERPRETATION = "opinion_interpretation"  # Require balanced perspective sources

class CitationProcessor:
    def __init__(self):
        """Initialize the citation processor with Azure OpenAI client."""
        self.azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "")
        self.azure_api_key = os.getenv("AZURE_OPENAI_API_KEY", "")
        self.azure_deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "")
        
        if not self.azure_endpoint:
            print("Warning: Azure OpenAI endpoint not found in environment variables")
            self.client = None
            self.model = None
            return
        if not self.azure_api_key:
            print("Warning: Azure OpenAI API key not found in environment variables")
            self.client = None
            self.model = None
            return
        if not self.azure_deployment:
            print("Warning: Azure OpenAI deployment name not found in environment variables")
            self.client = None
            self.model = None
            return
        
        # Initialize Azure OpenAI client
        self.client = AzureOpenAI(
            azure_endpoint=self.azure_endpoint,
            api_key=self.azure_api_key,
            api_version="2024-02-01"
        )
        self.model = self.azure_deployment
        
    def process_paper(self, paper_content: str, pdf_library, bibliography_parser=None, citation_formatter=None) -> Optional[Dict[str, Any]]:
        """
        Main processing function that analyzes paper and inserts citations.
        
        Args:
            paper_content: The original paper text
            pdf_library: PDFLibrary instance containing source documents
            bibliography_parser: BibliographyParser instance for enhanced citations (optional)
            
        Returns:
            Dictionary containing processed results
        """
        # Check if OpenAI client is available
        if not self.client:
            print("Warning: Citation processing unavailable - OpenAI client not configured")
            return {
                'original_text': paper_content,
                'cited_text': paper_content,
                'citations': [],
                'references': '',
                'stats': {
                    'claims_identified': 0,
                    'citations_added': 0,
                    'sources_used': 0
                },
                'error': 'OpenAI client not configured'
            }
        
        try:
            # CRITICAL FIX: Store references for citation generation BEFORE any authority scoring
            # This ensures _calculate_source_authority has access to PDF metadata
            self.pdf_library = pdf_library
            self.bibliography_parser = bibliography_parser
            
            # Reset citation formatter state for new analysis (critical for IEEE numbering)
            if citation_formatter:
                citation_formatter.reset_state()
            
            # Step 1: Identify and categorize claims requiring citations
            claims = self._identify_claims(paper_content)
            
            if not claims:
                return {
                    'original_text': paper_content,
                    'cited_text': paper_content,
                    'citations': [],
                    'references': '',
                    'stats': {
                        'claims_identified': 0,
                        'citations_added': 0,
                        'sources_used': 0
                    }
                }
            
            # Step 2: Find supporting content for each categorized claim
            citations_found = []
            cited_text = paper_content
            
            for claim_obj in claims:
                claim_text = claim_obj.get('text', '') if isinstance(claim_obj, dict) else str(claim_obj)
                claim_type = claim_obj.get('type', 'FACTUAL') if isinstance(claim_obj, dict) else 'FACTUAL'
                claim_reasoning = claim_obj.get('reasoning', '') if isinstance(claim_obj, dict) else ''
                
                supporting_content = self._find_supporting_content(
                    claim_text, 
                    pdf_library, 
                    bibliography_parser, 
                    citation_formatter,
                    claim_type=claim_type
                )
                if supporting_content:
                    citations_found.append({
                        'claim': claim_text,
                        'claim_type': claim_type,
                        'claim_reasoning': claim_reasoning,
                        'source': supporting_content['source'],
                        'quote': supporting_content['quote'],
                        'page': supporting_content['page'],
                        'citation': supporting_content['citation'],
                        'source_authority_score': supporting_content.get('authority_score', 0.5)
                    })
                    
                    # Insert citation into text
                    cited_text = self._insert_citation(
                        cited_text, 
                        claim_text, 
                        supporting_content,
                        citation_formatter
                    )
            
            # Step 3: Generate references list
            references = self._generate_references_list(citations_found, citation_formatter)
            
            # Calculate statistics
            unique_sources = len(set(citation['source'] for citation in citations_found))
            
            return {
                'original_text': paper_content,
                'cited_text': cited_text,
                'citations': citations_found,
                'references': references,
                'stats': {
                    'claims_identified': len(claims),
                    'citations_added': len(citations_found),
                    'sources_used': unique_sources
                }
            }
            
        except Exception as e:
            print(f"Error processing paper: {str(e)}")
            return None
    
    def _identify_claims(self, text: str) -> List[Dict[str, str]]:
        """
        Identify and categorize claims in the text that require citations using OpenAI.
        
        Args:
            text: The paper content
            
        Returns:
            List of dictionaries containing claims and their categories
        """
        try:
            prompt = f"""
            You are an academic writing assistant. Analyze the following research paper text and identify statements that require academic citations according to academic writing standards, then categorize each claim.

            CLAIM TYPES TO IDENTIFY:
            1. FACTUAL: Objective statements about established facts, historical events, or research findings
            2. STATISTICAL: Numerical data, percentages, measurements, or quantitative research results
            3. THEORETICAL: Concepts, frameworks, models, or abstract theoretical discussions
            4. METHODOLOGICAL: Research methods, procedures, techniques, or experimental approaches
            5. OPINION_INTERPRETATION: Subjective interpretations, analysis, or debatable viewpoints

            CITATION REQUIREMENTS BY TYPE:
            - FACTUAL: Requires authoritative, primary sources
            - STATISTICAL: Requires data sources with clear methodology
            - THEORETICAL: Requires foundational academic sources
            - METHODOLOGICAL: Requires peer-reviewed research methods
            - OPINION_INTERPRETATION: Requires balanced perspective sources

            Look for statements that require citations but DO NOT flag:
            - Personal opinions clearly marked as such
            - Common knowledge statements
            - Methodology descriptions of the current study
            - Obvious facts

            Text to analyze:
            {text}

            Return your response as JSON with this format:
            {{
                "claims": [
                    {{
                        "text": "First claim requiring citation...",
                        "type": "FACTUAL",
                        "reasoning": "Brief explanation why this claim needs this type of citation"
                    }},
                    {{
                        "text": "Second claim requiring citation...",
                        "type": "STATISTICAL", 
                        "reasoning": "Brief explanation why this claim needs this type of citation"
                    }}
                ]
            }}
            """
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            
            content = response.choices[0].message.content
            if content is None:
                return []
            result = json.loads(content)
            return result.get('claims', [])
            
        except Exception as e:
            print(f"Error identifying claims: {str(e)}")
            return []
    
    def _find_supporting_content(self, claim: str, pdf_library, bibliography_parser=None, citation_formatter=None, claim_type: str = 'FACTUAL') -> Optional[Dict[str, str]]:
        """
        Find supporting content for a claim in the PDF library using claim-type aware strategies.
        
        Args:
            claim: The claim needing support
            pdf_library: PDFLibrary instance
            bibliography_parser: BibliographyParser instance for enhanced citations (optional)
            citation_formatter: CitationFormatter instance
            claim_type: Type of claim (FACTUAL, STATISTICAL, THEORETICAL, METHODOLOGICAL, OPINION_INTERPRETATION)
            
        Returns:
            Dictionary with supporting content and authority score, or None
        """
        try:
            # Get all content from PDF library
            library_content = pdf_library.get_all_content()
            
            if not library_content:
                return None
            
            # Use semantic search to find most relevant content
            best_match = self._semantic_search(claim, library_content)
            
            if not best_match:
                return None
            
            # Calculate authority score based on claim type and source characteristics
            authority_score = self._calculate_source_authority(best_match, claim_type, bibliography_parser)
            
            # Apply claim-type specific filtering
            if not self._is_source_appropriate_for_claim_type(best_match, claim_type, authority_score):
                # Try to find a better match with higher authority
                alternative_matches = self._get_alternative_matches(claim, library_content, claim_type, bibliography_parser)
                if alternative_matches:
                    best_match = alternative_matches[0]
                    authority_score = self._calculate_source_authority(best_match, claim_type, bibliography_parser)
                else:
                    # Use original match but note low authority
                    pass
            
            # Extract a relevant quote using OpenAI
            quote_info = self._extract_supporting_quote(claim, best_match)
            
            if quote_info:
                # Generate citation for this source using selected style
                citation = self._generate_citation(best_match['filename'], citation_formatter) if citation_formatter else self._generate_fallback_citation(best_match['filename'])
                
                return {
                    'source': best_match['filename'],
                    'quote': quote_info['quote'],
                    'page': quote_info['page'],
                    'citation': citation,
                    'authority_score': authority_score,
                    'claim_type_match': self._evaluate_claim_type_match(best_match, claim_type)
                }
            
            return None
            
        except Exception as e:
            print(f"Error finding supporting content: {str(e)}")
            return None
    
    def _calculate_source_authority(self, source: Dict, claim_type: str, bibliography_parser=None) -> float:
        """
        Calculate authority score for a source based on claim type and source characteristics.
        
        Args:
            source: Source content dictionary
            claim_type: Type of claim needing support
            bibliography_parser: BibliographyParser for enhanced metadata
            
        Returns:
            Authority score from 0.0 to 1.0
        """
        try:
            score = 0.5  # Base score
            filename = source.get('filename', '')
            
            # Get enhanced metadata if available
            metadata = {}
            if hasattr(self, 'pdf_library'):
                pdf_content = self.pdf_library.get_pdf_content(filename)
                if pdf_content:
                    metadata = pdf_content.get('metadata', {})
            
            # Enhance with bibliography data
            bib_entry = None
            if bibliography_parser:
                bib_entry = bibliography_parser.find_matching_entry(filename, metadata)
                if bib_entry:
                    metadata.update(self._convert_bibliography_to_metadata(bib_entry))
            
            # Authority factors based on claim type
            if claim_type == 'FACTUAL':
                # Prefer authoritative, primary sources
                if metadata.get('journal'):
                    score += 0.2  # Published in journal
                if metadata.get('doi'):
                    score += 0.1  # Has DOI
                if metadata.get('publisher') and 'university' in metadata.get('publisher', '').lower():
                    score += 0.1  # University press
                    
            elif claim_type == 'STATISTICAL':
                # Prefer data sources with methodology
                if metadata.get('journal'):
                    score += 0.3  # Journal article likely has methodology
                if any(term in filename.lower() for term in ['data', 'study', 'survey', 'analysis']):
                    score += 0.2  # Likely contains data
                if metadata.get('year'):
                    try:
                        year = int(metadata['year'])
                        if year >= 2015:  # Recent data preferred
                            score += 0.1
                    except (ValueError, TypeError):
                        pass
                        
            elif claim_type == 'THEORETICAL':
                # Prefer foundational academic sources
                if metadata.get('journal'):
                    score += 0.2
                if metadata.get('year'):
                    try:
                        year = int(metadata['year'])
                        if year <= 2000:  # Older foundational work valued
                            score += 0.1
                        elif year >= 2010:  # Also value recent theory
                            score += 0.05
                    except (ValueError, TypeError):
                        pass
                if any(term in filename.lower() for term in ['theory', 'framework', 'model', 'concept']):
                    score += 0.15
                    
            elif claim_type == 'METHODOLOGICAL':
                # Prefer peer-reviewed research methods
                if metadata.get('journal'):
                    score += 0.3  # Strong preference for peer-reviewed
                if any(term in filename.lower() for term in ['method', 'procedure', 'protocol', 'technique']):
                    score += 0.2
                if metadata.get('doi'):
                    score += 0.1
                    
            elif claim_type == 'OPINION_INTERPRETATION':
                # Value balanced perspectives and recent analysis
                if metadata.get('year'):
                    try:
                        year = int(metadata['year'])
                        if year >= 2018:  # Recent perspectives valued
                            score += 0.15
                    except (ValueError, TypeError):
                        pass
                if metadata.get('journal'):
                    score += 0.1  # Academic discussion
                if any(term in filename.lower() for term in ['analysis', 'perspective', 'discussion', 'review']):
                    score += 0.1
            
            # General quality indicators
            if metadata.get('author'):
                score += 0.05  # Has identified author
            if metadata.get('title'):
                score += 0.05  # Has proper title
                
            return min(score, 1.0)  # Cap at 1.0
            
        except Exception as e:
            print(f"Error calculating source authority: {str(e)}")
            return 0.5
    
    def _is_source_appropriate_for_claim_type(self, source: Dict, claim_type: str, authority_score: float) -> bool:
        """
        Check if source meets minimum requirements for claim type.
        
        Args:
            source: Source content dictionary
            claim_type: Type of claim
            authority_score: Calculated authority score
            
        Returns:
            True if source is appropriate for claim type
        """
        try:
            # Minimum thresholds by claim type
            thresholds = {
                'FACTUAL': 0.6,  # High threshold for factual claims
                'STATISTICAL': 0.65,  # Very high threshold for data claims
                'THEORETICAL': 0.55,  # Moderate threshold for theory
                'METHODOLOGICAL': 0.7,  # Highest threshold for methods
                'OPINION_INTERPRETATION': 0.4  # Lower threshold for opinions
            }
            
            threshold = thresholds.get(claim_type, 0.5)
            return authority_score >= threshold
            
        except Exception as e:
            print(f"Error checking source appropriateness: {str(e)}")
            return True  # Default to allowing source
    
    def _get_alternative_matches(self, claim: str, library_content: List[Dict], claim_type: str, bibliography_parser=None) -> List[Dict]:
        """
        Find alternative source matches ranked by authority for the claim type.
        
        Args:
            claim: Original claim text
            library_content: All available library content
            claim_type: Type of claim needing support
            bibliography_parser: BibliographyParser instance
            
        Returns:
            List of alternative sources ranked by authority
        """
        try:
            # Get multiple matches using semantic search
            texts = [claim] + [content['text'] for content in library_content]
            
            vectorizer = TfidfVectorizer(stop_words='english', max_features=1000)
            tfidf_matrix = vectorizer.fit_transform(texts)
            
            claim_vector = tfidf_matrix[0]
            content_vectors = tfidf_matrix[1:]
            
            similarities = cosine_similarity(claim_vector, content_vectors).flatten()
            
            # Get top matches above threshold
            threshold = 0.05  # Lower threshold for alternatives
            candidate_indices = [i for i, sim in enumerate(similarities) if sim > threshold]
            
            # Calculate authority scores for candidates
            candidates_with_scores = []
            for idx in candidate_indices:
                source = library_content[idx]
                authority_score = self._calculate_source_authority(source, claim_type, bibliography_parser)
                candidates_with_scores.append({
                    'source': source,
                    'similarity': similarities[idx],
                    'authority': authority_score,
                    'combined_score': similarities[idx] * 0.4 + authority_score * 0.6  # Weight authority higher
                })
            
            # Sort by combined score (authority-weighted)
            candidates_with_scores.sort(key=lambda x: x['combined_score'], reverse=True)
            
            # Return top alternative sources
            return [c['source'] for c in candidates_with_scores[:3]]
            
        except Exception as e:
            print(f"Error finding alternative matches: {str(e)}")
            return []
    
    def _evaluate_claim_type_match(self, source: Dict, claim_type: str) -> str:
        """
        Evaluate how well the source matches the claim type requirements.
        
        Args:
            source: Source content dictionary
            claim_type: Type of claim
            
        Returns:
            Match evaluation string
        """
        try:
            filename = source.get('filename', '').lower()
            
            # Type-specific matching logic
            if claim_type == 'FACTUAL':
                if any(term in filename for term in ['report', 'study', 'research', 'data']):
                    return "Strong match - authoritative source"
                return "Moderate match - general source"
                
            elif claim_type == 'STATISTICAL':
                if any(term in filename for term in ['data', 'statistics', 'survey', 'analysis']):
                    return "Strong match - data source"
                elif any(term in filename for term in ['study', 'research']):
                    return "Good match - research source"
                return "Weak match - limited data evidence"
                
            elif claim_type == 'THEORETICAL':
                if any(term in filename for term in ['theory', 'framework', 'model']):
                    return "Strong match - theoretical source"
                elif any(term in filename for term in ['concept', 'principle']):
                    return "Good match - conceptual source"
                return "Moderate match - general academic source"
                
            elif claim_type == 'METHODOLOGICAL':
                if any(term in filename for term in ['method', 'protocol', 'procedure']):
                    return "Strong match - methodological source"
                elif any(term in filename for term in ['technique', 'approach']):
                    return "Good match - procedural source"
                return "Weak match - limited methodological detail"
                
            elif claim_type == 'OPINION_INTERPRETATION':
                if any(term in filename for term in ['analysis', 'perspective', 'review']):
                    return "Strong match - analytical source"
                elif any(term in filename for term in ['discussion', 'commentary']):
                    return "Good match - interpretive source"
                return "Moderate match - general source"
                
            return "General match"
            
        except Exception as e:
            print(f"Error evaluating claim type match: {str(e)}")
            return "Match evaluation unavailable"
    
    def _semantic_search(self, claim: str, library_content: List[Dict]) -> Optional[Dict]:
        """
        Perform semantic search to find the most relevant content.
        
        Args:
            claim: The claim to search for
            library_content: List of content from PDF library
            
        Returns:
            Best matching content or None
        """
        try:
            if not library_content:
                return None
            
            # Prepare texts for vectorization
            texts = [claim] + [content['text'] for content in library_content]
            
            # Create TF-IDF vectors
            vectorizer = TfidfVectorizer(stop_words='english', max_features=1000)
            tfidf_matrix = vectorizer.fit_transform(texts)
            
            # Calculate similarity scores
            claim_vector = tfidf_matrix[0]
            content_vectors = tfidf_matrix[1:]
            
            similarities = cosine_similarity(claim_vector, content_vectors).flatten()
            
            # Find best match above threshold
            threshold = 0.1  # Minimum similarity threshold
            best_idx = np.argmax(similarities)
            
            if similarities[best_idx] > threshold:
                return library_content[best_idx]
            
            return None
            
        except Exception as e:
            print(f"Error in semantic search: {str(e)}")
            return None
    
    def _extract_supporting_quote(self, claim: str, content: Dict) -> Optional[Dict[str, str]]:
        """
        Extract a supporting quote from content using OpenAI.
        
        Args:
            claim: The claim needing support
            content: Content dictionary with text and page info
            
        Returns:
            Dictionary with quote and page info
        """
        try:
            prompt = f"""
            You are helping with academic citation. Given a claim and a source text, extract the most relevant and supportive quote.

            Claim: {claim}

            Source text: {content['text'][:2000]}  # Limit text length

            Extract a concise quote (1-3 sentences) that best supports the claim. The quote should:
            - Directly relate to the claim
            - Be self-contained and understandable
            - Be an exact excerpt from the source text
            - Not be too long (maximum 150 words)

            Return your response as JSON:
            {{
                "quote": "Exact quote from the source text that supports the claim",
                "relevance_score": 0.8
            }}

            If no relevant quote is found, return:
            {{
                "quote": "",
                "relevance_score": 0.0
            }}
            """
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            
            response_content = response.choices[0].message.content
            if response_content is None:
                return None
            result = json.loads(response_content)
            
            if result.get('relevance_score', 0) > 0.5 and result.get('quote'):
                return {
                    'quote': result['quote'],
                    'page': str(content.get('page', 'N/A'))
                }
            
            return None
            
        except Exception as e:
            print(f"Error extracting quote: {str(e)}")
            return None
    
    def _generate_citation(self, filename: str, citation_formatter) -> str:
        """
        Generate citation using bibliography data or PDF metadata in the selected style.
        
        Args:
            filename: PDF filename
            citation_formatter: CitationFormatter instance with selected style
            
        Returns:
            Citation format using best available data and selected style
        """
        try:
            # Try to get bibliography entry first (higher quality data)
            bibliography_entry = None
            if hasattr(self, 'bibliography_parser') and self.bibliography_parser:
                pdf_content = self.pdf_library.get_pdf_content(filename) if hasattr(self, 'pdf_library') else None
                if pdf_content:
                    bibliography_entry = self.bibliography_parser.find_matching_entry(
                        filename, 
                        pdf_content.get('metadata', {})
                    )
            
            if bibliography_entry:
                # Use bibliography data for citation
                source_info = {
                    'filename': filename,
                    'metadata': self._convert_bibliography_to_metadata(bibliography_entry)
                }
                return citation_formatter.format_citation(source_info)
            
            # Fall back to PDF metadata
            pdf_content = self.pdf_library.get_pdf_content(filename) if hasattr(self, 'pdf_library') else None
            if pdf_content:
                source_info = {
                    'filename': filename,
                    'metadata': pdf_content.get('metadata', {})
                }
                return citation_formatter.format_citation(source_info)
            
            # Final fallback: filename-based
            return self._generate_fallback_citation(filename)
                
        except Exception as e:
            print(f"Error generating citation: {str(e)}")
            return self._generate_fallback_citation(filename)
    
    def _generate_fallback_citation(self, filename: str) -> str:
        """
        Generate a simple fallback citation when formatter is unavailable.
        
        Args:
            filename: PDF filename
            
        Returns:
            Simple citation format
        """
        title = filename.replace('.pdf', '').replace('_', ' ').replace('-', ' ')
        return f"{title} (n.d.)."
    
    def _convert_bibliography_to_metadata(self, bib_entry: Dict) -> Dict:
        """
        Convert bibliography entry format to metadata format.
        
        Args:
            bib_entry: Bibliography entry dictionary
            
        Returns:
            Metadata dictionary compatible with enhanced CitationFormatter
        """
        try:
            # Convert authors list to single string
            authors_str = ""
            if bib_entry.get('authors'):
                authors_str = ", ".join(bib_entry['authors'])
            
            # Extract enhanced academic fields
            return {
                'title': bib_entry.get('title', ''),
                'author': authors_str,
                'creation_date': bib_entry.get('year', ''),
                'subject': bib_entry.get('journal', ''),  # Keep for backward compatibility
                'journal': bib_entry.get('journal', ''),
                'volume': bib_entry.get('volume', ''),
                'issue': bib_entry.get('issue', ''),
                'pages': bib_entry.get('pages', ''),
                'publisher': bib_entry.get('publisher', ''),
                'doi': bib_entry.get('doi', ''),
                'url': bib_entry.get('url', ''),
                'isbn': bib_entry.get('isbn', ''),
                'issn': bib_entry.get('issn', ''),
                'editor': bib_entry.get('editor', ''),
                'edition': bib_entry.get('edition', ''),
                'place': bib_entry.get('place', ''),
                'conference': bib_entry.get('conference', ''),
                'book_title': bib_entry.get('book_title', ''),  # For book chapters
                'series': bib_entry.get('series', '')
            }
        except Exception as e:
            print(f"Error converting bibliography to metadata: {str(e)}")
            return {}
    
    def _insert_citation(self, text: str, claim: str, supporting_content: Dict, citation_formatter=None) -> str:
        """
        Insert citation and quote into the text after the claim.
        
        Args:
            text: Original text
            claim: The claim to cite
            supporting_content: Supporting content info
            
        Returns:
            Text with citation inserted
        """
        try:
            # Find the claim in the text
            claim_position = text.find(claim)
            
            if claim_position == -1:
                # If exact match not found, try partial matching
                sentences = nltk.sent_tokenize(text)
                for sentence in sentences:
                    if self._sentences_similar(claim, sentence):
                        claim_position = text.find(sentence)
                        claim = sentence
                        break
            
            if claim_position != -1:
                # Create proper in-text citation using selected formatter
                if citation_formatter:
                    # Get source info for proper in-text citation
                    pdf_content = self.pdf_library.get_pdf_content(supporting_content['source']) if hasattr(self, 'pdf_library') else None
                    
                    if pdf_content:
                        source_info = {
                            'filename': supporting_content['source'],
                            'metadata': pdf_content.get('metadata', {})
                        }
                        citation_text = f" {citation_formatter.format_in_text_citation(source_info, supporting_content['page'])}"
                    else:
                        # Fallback to basic format
                        citation_text = f" ({supporting_content['citation'].split('(')[0].strip()}, {supporting_content['page']})"
                else:
                    # Fallback when no formatter provided
                    citation_text = f" ({supporting_content['citation'].split('(')[0].strip()}, {supporting_content['page']})"
                
                quote_text = f' "{supporting_content["quote"]}"'
                
                # Insert after the claim
                insert_position = claim_position + len(claim)
                
                # Insert citation and quote
                new_text = (
                    text[:insert_position] + 
                    citation_text + 
                    quote_text + 
                    text[insert_position:]
                )
                
                return new_text
            
            return text
            
        except Exception as e:
            print(f"Error inserting citation: {str(e)}")
            return text
    
    def _sentences_similar(self, sent1: str, sent2: str, threshold: float = 0.7) -> bool:
        """
        Check if two sentences are similar using TF-IDF similarity.
        
        Args:
            sent1: First sentence
            sent2: Second sentence
            threshold: Similarity threshold
            
        Returns:
            True if sentences are similar
        """
        try:
            vectorizer = TfidfVectorizer(stop_words='english')
            tfidf_matrix = vectorizer.fit_transform([sent1, sent2])
            similarity = cosine_similarity(tfidf_matrix[0], tfidf_matrix[1])[0][0]
            return similarity > threshold
        except:
            return False
    
    def _generate_references_list(self, citations: List[Dict], citation_formatter=None) -> str:
        """
        Generate references list from citations using selected citation formatter.
        
        Args:
            citations: List of citation dictionaries
            citation_formatter: CitationFormatter instance with selected style
            
        Returns:
            Formatted references list
        """
        if not citations:
            return ""
        
        try:
            if citation_formatter:
                # Enhance citations with comprehensive metadata for better reference formatting
                enhanced_citations = []
                for citation in citations:
                    enhanced_citation = citation.copy()
                    
                    # Start with empty metadata
                    comprehensive_metadata = {}
                    
                    # Get PDF metadata if available
                    if hasattr(self, 'pdf_library'):
                        pdf_content = self.pdf_library.get_pdf_content(citation['source'])
                        if pdf_content:
                            comprehensive_metadata.update(pdf_content.get('metadata', {}))
                    
                    # Enhance with bibliography metadata if available and more complete
                    if hasattr(self, 'bibliography_parser') and self.bibliography_parser:
                        bib_entry = self.bibliography_parser.find_matching_entry(
                            citation['source'], 
                            comprehensive_metadata
                        )
                        if bib_entry:
                            # Merge bibliography data with PDF metadata
                            # Bibliography data takes precedence for bibliographic fields
                            bibliographic_fields = {
                                'title': bib_entry.get('title', ''),
                                'authors': bib_entry.get('authors', []),
                                'author': ', '.join(bib_entry.get('authors', [])),  # For compatibility
                                'year': bib_entry.get('year', ''),
                                'journal': bib_entry.get('journal', ''),
                                'volume': bib_entry.get('volume', ''),
                                'issue': bib_entry.get('issue', ''),
                                'pages': bib_entry.get('pages', ''),
                                'doi': bib_entry.get('doi', ''),
                                'url': bib_entry.get('url', ''),
                                'publisher': bib_entry.get('publisher', ''),
                                'editor': bib_entry.get('editor', ''),
                                'edition': bib_entry.get('edition', ''),
                                'type': bib_entry.get('type', 'unknown')
                            }
                            
                            # Update comprehensive metadata with non-empty bibliography fields
                            for field, value in bibliographic_fields.items():
                                if value:  # Only use non-empty bibliography values
                                    comprehensive_metadata[field] = value
                                elif field not in comprehensive_metadata:
                                    comprehensive_metadata[field] = value  # Set empty default if not in PDF metadata
                    
                    # Ensure we have essential fields even if empty
                    essential_fields = ['title', 'authors', 'author', 'year', 'journal', 'volume', 'issue', 'pages', 'doi', 'url', 'publisher']
                    for field in essential_fields:
                        if field not in comprehensive_metadata:
                            comprehensive_metadata[field] = '' if field != 'authors' else []
                    
                    enhanced_citation['metadata'] = comprehensive_metadata
                    enhanced_citations.append(enhanced_citation)
                
                # Use selected formatter for proper reference list formatting
                return citation_formatter.format_reference_list(enhanced_citations)
            else:
                # Fallback when no formatter provided
                return self._generate_fallback_references_list(citations)
            
        except Exception as e:
            print(f"Error generating references with formatter: {str(e)}")
            return self._generate_fallback_references_list(citations)
    
    def _generate_fallback_references_list(self, citations: List[Dict]) -> str:
        """
        Generate a simple fallback references list when formatter is unavailable.
        
        Args:
            citations: List of citation dictionaries
            
        Returns:
            Simple formatted references list
        """
        references = []
        seen_sources = set()
        
        for citation in citations:
            source = citation['source']
            if source not in seen_sources:
                references.append(citation.get('citation', citation.get('apa_citation', source)))
                seen_sources.add(source)
        
        # Sort alphabetically by author (simplified)
        references.sort()
        
        references_text = "References\n\n" + "\n\n".join(references)
        return references_text
