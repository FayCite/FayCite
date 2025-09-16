import re
from typing import Dict, List, Optional
from datetime import datetime

class BibliographyParser:
    def __init__(self):
        """Initialize the bibliography parser."""
        self.entries = {}  # title -> entry mapping
        self.raw_entries = []  # List of all parsed entries
        
    def parse_zotero_txt(self, file_content: str) -> bool:
        """
        Parse Zotero bibliography .txt file content.
        
        Args:
            file_content: Content of the bibliography file
            
        Returns:
            True if successfully parsed, False otherwise
        """
        try:
            # Clear existing data to prevent accumulation across uploads
            self.entries.clear()
            self.raw_entries.clear()
            
            # Split by double newlines to separate entries
            raw_entries = file_content.strip().split('\n\n')
            
            parsed_entries = []
            
            for raw_entry in raw_entries:
                entry = self._parse_single_entry(raw_entry.strip())
                if entry:
                    parsed_entries.append(entry)
                    # Index by title for quick lookup
                    title = entry.get('title', '').lower()
                    if title:
                        self.entries[title] = entry
            
            self.raw_entries = parsed_entries
            return len(parsed_entries) > 0
            
        except Exception as e:
            print(f"Error parsing bibliography: {str(e)}")
            return False
    
    def _parse_single_entry(self, entry_text: str) -> Optional[Dict]:
        """
        Parse a single bibliography entry.
        
        Args:
            entry_text: Single bibliography entry text
            
        Returns:
            Dictionary with parsed entry or None
        """
        try:
            entry = {
                'raw_text': entry_text,
                'title': '',
                'authors': [],
                'year': '',
                'journal': '',
                'volume': '',
                'issue': '',
                'pages': '',
                'doi': '',
                'url': '',
                'type': 'unknown'
            }
            
            # Extract year - look for (YYYY) pattern
            year_match = re.search(r'\((\d{4})\)', entry_text)
            if year_match:
                entry['year'] = year_match.group(1)
            
            # Extract DOI
            doi_match = re.search(r'doi:([^\s]+)', entry_text, re.IGNORECASE)
            if doi_match:
                entry['doi'] = doi_match.group(1)
            
            # Extract URL
            url_match = re.search(r'https?://[^\s]+', entry_text)
            if url_match:
                entry['url'] = url_match.group(0)
            
            # Determine entry type and extract accordingly
            if 'Journal' in entry_text or 'journal' in entry_text.lower():
                entry = self._parse_journal_entry(entry_text, entry)
            elif 'Book' in entry_text or 'book' in entry_text.lower():
                entry = self._parse_book_entry(entry_text, entry)
            else:
                entry = self._parse_generic_entry(entry_text, entry)
            
            return entry if entry['title'] else None
            
        except Exception as e:
            print(f"Error parsing single entry: {str(e)}")
            return None
    
    def _parse_journal_entry(self, text: str, entry: Dict) -> Dict:
        """Parse journal article entry."""
        entry['type'] = 'journal'
        
        # Common journal article patterns
        # Author, A. A. (Year). Title. Journal, Volume(Issue), pages.
        
        # Extract title (usually after year and before journal)
        title_pattern = r'\(\d{4}\)\.\s*([^.]+)\.\s*[A-Z]'
        title_match = re.search(title_pattern, text)
        if title_match:
            entry['title'] = title_match.group(1).strip()
        
        # Extract authors (usually at the beginning)
        author_pattern = r'^([^(]+)\s*\('
        author_match = re.search(author_pattern, text)
        if author_match:
            authors_text = author_match.group(1).strip()
            # Split by commas and clean up
            authors = [author.strip() for author in authors_text.split(',') if author.strip()]
            entry['authors'] = authors
        
        # Extract journal name, volume, issue, pages
        journal_pattern = r'([A-Z][^,]+),\s*(\d+)(?:\((\d+)\))?,\s*([^.]+)\.'
        journal_match = re.search(journal_pattern, text)
        if journal_match:
            entry['journal'] = journal_match.group(1).strip()
            entry['volume'] = journal_match.group(2)
            entry['issue'] = journal_match.group(3) or ''
            entry['pages'] = journal_match.group(4).strip()
        
        return entry
    
    def _parse_book_entry(self, text: str, entry: Dict) -> Dict:
        """Parse book entry."""
        entry['type'] = 'book'
        
        # Extract title and authors for books
        # Author, A. A. (Year). Title. Publisher.
        
        # Extract title
        title_pattern = r'\(\d{4}\)\.\s*([^.]+)\.'
        title_match = re.search(title_pattern, text)
        if title_match:
            entry['title'] = title_match.group(1).strip()
        
        # Extract authors
        author_pattern = r'^([^(]+)\s*\('
        author_match = re.search(author_pattern, text)
        if author_match:
            authors_text = author_match.group(1).strip()
            authors = [author.strip() for author in authors_text.split(',') if author.strip()]
            entry['authors'] = authors
        
        return entry
    
    def _parse_generic_entry(self, text: str, entry: Dict) -> Dict:
        """Parse generic entry when type is unclear."""
        # Try to extract basic info
        
        # Extract title (text between year and next period/comma)
        title_pattern = r'\(\d{4}\)[^.]*?\.\s*([^.,]+)'
        title_match = re.search(title_pattern, text)
        if title_match:
            entry['title'] = title_match.group(1).strip()
        
        # If no title found, try alternative patterns
        if not entry['title']:
            # Sometimes title comes first
            first_period = text.find('.')
            if first_period > 0:
                potential_title = text[:first_period].strip()
                if len(potential_title) > 10 and '(' not in potential_title:
                    entry['title'] = potential_title
        
        # Extract authors
        author_pattern = r'^([^(]+)\s*\('
        author_match = re.search(author_pattern, text)
        if author_match:
            authors_text = author_match.group(1).strip()
            authors = [author.strip() for author in authors_text.split(',') if author.strip()]
            entry['authors'] = authors
        
        return entry
    
    def find_matching_entry(self, pdf_filename: str, pdf_metadata: Dict) -> Optional[Dict]:
        """
        Find bibliography entry that matches a PDF.
        
        Args:
            pdf_filename: Name of the PDF file
            pdf_metadata: Metadata extracted from PDF
            
        Returns:
            Matching bibliography entry or None
        """
        try:
            # Clean up filename for comparison
            filename_title = pdf_filename.replace('.pdf', '').replace('_', ' ').replace('-', ' ').lower()
            
            # Try exact title match from metadata
            pdf_title = pdf_metadata.get('title', '').lower().strip()
            if pdf_title and pdf_title in self.entries:
                return self.entries[pdf_title]
            
            # Try fuzzy matching with filename
            for title, entry in self.entries.items():
                if self._titles_similar(filename_title, title):
                    return entry
            
            # Try matching by author
            pdf_author = pdf_metadata.get('author', '').lower().strip()
            if pdf_author:
                for entry in self.raw_entries:
                    for author in entry.get('authors', []):
                        if author.lower() in pdf_author or pdf_author in author.lower():
                            return entry
            
            return None
            
        except Exception as e:
            print(f"Error finding matching entry: {str(e)}")
            return None
    
    def _titles_similar(self, title1: str, title2: str, threshold: float = 0.6) -> bool:
        """
        Check if two titles are similar using simple word overlap.
        
        Args:
            title1: First title
            title2: Second title
            threshold: Similarity threshold
            
        Returns:
            True if titles are similar
        """
        try:
            words1 = set(title1.lower().split())
            words2 = set(title2.lower().split())
            
            if not words1 or not words2:
                return False
            
            intersection = words1.intersection(words2)
            union = words1.union(words2)
            
            similarity = len(intersection) / len(union) if union else 0
            return similarity >= threshold
            
        except Exception:
            return False
    
    def get_entry_by_title(self, title: str) -> Optional[Dict]:
        """Get bibliography entry by title."""
        return self.entries.get(title.lower(), None)
    
    def get_all_entries(self) -> List[Dict]:
        """Get all bibliography entries."""
        return self.raw_entries.copy()
    
    def get_statistics(self) -> Dict:
        """Get statistics about the bibliography."""
        types = {}
        for entry in self.raw_entries:
            entry_type = entry.get('type', 'unknown')
            types[entry_type] = types.get(entry_type, 0) + 1
        
        return {
            'total_entries': len(self.raw_entries),
            'types': types,
            'entries_with_doi': len([e for e in self.raw_entries if e.get('doi')]),
            'entries_with_year': len([e for e in self.raw_entries if e.get('year')])
        }