import re
from typing import Dict, List, Optional
from datetime import datetime

class APAFormatter:
    def __init__(self):
        """Initialize the APA formatter."""
        self.current_year = datetime.now().year
    
    def format_citation(self, source_info: Dict) -> str:
        """
        Format a citation in APA style.
        
        Args:
            source_info: Dictionary containing source information
            
        Returns:
            Formatted APA citation
        """
        try:
            # Extract available information
            filename = source_info.get('filename', '')
            metadata = source_info.get('metadata', {})
            
            # Try to extract author from metadata or filename
            author = self._extract_author(metadata, filename)
            year = self._extract_year(metadata, filename)
            title = self._extract_title(metadata, filename)
            
            # Format basic citation following APA guidelines
            if author and year:
                return f"{author} ({year}). {title}."
            elif author:
                return f"{author} (n.d.). {title}."
            elif year:
                # Title-first format when no author (APA compliance)
                return f"{title} ({year})."
            else:
                return f"{title} (n.d.)."
                
        except Exception as e:
            print(f"Error formatting citation: {str(e)}")
            return source_info.get('filename', 'Unknown source')
    
    def format_in_text_citation(self, source_info: Dict, page: Optional[str] = None) -> str:
        """
        Format an in-text citation in APA style.
        
        Args:
            source_info: Dictionary containing source information
            page: Page number (optional)
            
        Returns:
            Formatted in-text citation
        """
        try:
            metadata = source_info.get('metadata', {})
            filename = source_info.get('filename', '')
            
            author = self._extract_author(metadata, filename, short_form=True)
            year = self._extract_year(metadata, filename)
            
            if author and year:
                base_citation = f"({author}, {year}"
            elif author:
                base_citation = f"({author}, n.d."
            else:
                # APA title-first format when no author - use first word of title
                title = self._extract_title(metadata, filename)
                first_word = title.split()[0] if title else "Unknown"
                year_part = year if year else "n.d."
                base_citation = f"({first_word}, {year_part}"
            
            if page:
                return f"{base_citation}, p. {page})"
            else:
                return f"{base_citation})"
                
        except Exception as e:
            print(f"Error formatting in-text citation: {str(e)}")
            return "(Unknown, n.d.)"
    
    def format_reference_list(self, citations: List[Dict]) -> str:
        """
        Format a complete reference list in APA style.
        
        Args:
            citations: List of citation dictionaries
            
        Returns:
            Formatted reference list
        """
        try:
            references = []
            seen_sources = set()
            
            for citation in citations:
                source = citation.get('source', '')
                
                if source and source not in seen_sources:
                    ref = self._format_full_reference(citation)
                    if ref:
                        references.append(ref)
                        seen_sources.add(source)
            
            if not references:
                return ""
            
            # Sort references alphabetically
            references.sort()
            
            # Format the reference list
            reference_text = "References\n\n"
            for ref in references:
                reference_text += f"{ref}\n\n"
            
            return reference_text.strip()
            
        except Exception as e:
            print(f"Error formatting reference list: {str(e)}")
            return "References\n\nError formatting references."
    
    def _format_full_reference(self, citation: Dict) -> Optional[str]:
        """
        Format a full reference entry using available metadata.
        
        Args:
            citation: Citation dictionary with potential metadata
            
        Returns:
            Formatted reference or None
        """
        try:
            # Use metadata if available, otherwise fall back to filename parsing
            metadata = citation.get('metadata', {})
            filename = citation.get('source', '')
            
            author = self._extract_author(metadata, filename)
            year = self._extract_year(metadata, filename)
            title = self._extract_title(metadata, filename)
            
            # APA format for academic sources with proper title-first handling
            if author and year and title:
                return f"{author} ({year}). {title}."
            elif author and title:
                return f"{author} (n.d.). {title}."
            elif title:
                # Title-first format when no author (APA compliance)
                year_part = f"({year})" if year else "(n.d.)"
                return f"{title} {year_part}."
            else:
                return None
                
        except Exception as e:
            print(f"Error formatting full reference: {str(e)}")
            return None
    
    def _extract_author(self, metadata: Dict, filename: str, short_form: bool = False) -> str:
        """
        Extract author information from metadata or filename.
        
        Args:
            metadata: PDF metadata dictionary
            filename: Original filename
            short_form: Whether to return short form for in-text citations
            
        Returns:
            Author string
        """
        # Try metadata first
        author = metadata.get('author', '').strip()
        
        if author:
            if short_form:
                # For in-text citations, use last name only
                parts = author.split()
                if parts:
                    return parts[-1]  # Last name
            return author
        
        # Try to extract from filename
        filename_clean = filename.replace('.pdf', '')
        
        # Look for common patterns like "Author (Year)" or "Author - Title"
        author_patterns = [
            r'^([A-Za-z\s]+)\s*\(\d{4}\)',  # Author (Year)
            r'^([A-Za-z\s]+)\s*-',          # Author - Title
            r'^([A-Za-z\s]+)\s*_',          # Author_Title
        ]
        
        for pattern in author_patterns:
            match = re.search(pattern, filename_clean)
            if match:
                author = match.group(1).strip()
                if short_form:
                    parts = author.split()
                    if parts:
                        return parts[-1]
                return author
        
        # Default fallback - return empty string for proper APA title-first formatting
        return ""
    
    def _extract_year(self, metadata: Dict, filename: str) -> Optional[str]:
        """
        Extract year from metadata or filename.
        
        Args:
            metadata: PDF metadata dictionary
            filename: Original filename
            
        Returns:
            Year string or None
        """
        # Try metadata first
        creation_date = metadata.get('creation_date', '')
        if creation_date:
            year_match = re.search(r'(\d{4})', str(creation_date))
            if year_match:
                year = int(year_match.group(1))
                if 1900 <= year <= self.current_year:
                    return str(year)
        
        # Try filename
        year_matches = re.findall(r'(\d{4})', filename)
        for year_str in year_matches:
            year = int(year_str)
            if 1900 <= year <= self.current_year:
                return year_str
        
        return None
    
    def _extract_title(self, metadata: Dict, filename: str) -> str:
        """
        Extract title from metadata or filename.
        
        Args:
            metadata: PDF metadata dictionary
            filename: Original filename
            
        Returns:
            Title string
        """
        # Try metadata first
        title = metadata.get('title', '').strip()
        if title:
            return title
        
        # Clean up filename to create title
        title = filename.replace('.pdf', '')
        
        # Remove common patterns
        title = re.sub(r'\(\d{4}\)', '', title)  # Remove (Year)
        title = re.sub(r'^[A-Za-z\s]+-', '', title)  # Remove "Author -"
        title = re.sub(r'^[A-Za-z\s]+_', '', title)  # Remove "Author_"
        title = title.replace('_', ' ').replace('-', ' ')
        
        # Clean up spacing
        title = ' '.join(title.split())
        
        # Capitalize properly
        if title:
            return title.strip()
        
        return "Untitled Document"
    
    def validate_citation_format(self, citation: str) -> bool:
        """
        Validate if a citation follows basic APA format.
        
        Args:
            citation: Citation string to validate
            
        Returns:
            True if valid format
        """
        try:
            # Basic patterns for APA citations
            patterns = [
                r'^.+\s*\(\d{4}\)\..*',  # Author (Year). Title.
                r'^.+\s*\(n\.d\.\)\..*',  # Author (n.d.). Title.
                r'^\(.+,\s*\d{4}\)',      # (Author, Year)
                r'^\(.+,\s*n\.d\.\)',     # (Author, n.d.)
            ]
            
            for pattern in patterns:
                if re.match(pattern, citation):
                    return True
            
            return False
            
        except Exception:
            return False
    
    def get_citation_suggestions(self, text: str) -> List[str]:
        """
        Get suggestions for improving citation format.
        
        Args:
            text: Text to analyze
            
        Returns:
            List of suggestions
        """
        suggestions = []
        
        # Check for common issues
        if re.search(r'\d{4}', text) and not re.search(r'\(\d{4}\)', text):
            suggestions.append("Consider formatting years in parentheses: (2023)")
        
        if '&' in text:
            suggestions.append("Use 'and' instead of '&' in narrative citations")
        
        if re.search(r'pp?\.\s*\d+', text, re.IGNORECASE):
            suggestions.append("Page references should use 'p.' for single pages, 'pp.' for ranges")
        
        return suggestions
