import re
from typing import Dict, List, Optional
from datetime import datetime
from enum import Enum

class CitationStyle(Enum):
    """Enumeration of supported citation styles."""
    APA = "APA"
    MLA = "MLA" 
    CHICAGO = "Chicago"
    IEEE = "IEEE"

class CitationFormatter:
    def __init__(self, style: CitationStyle = CitationStyle.APA):
        """
        Initialize the citation formatter.
        
        Args:
            style: Citation style to use (APA, MLA, Chicago, IEEE)
        """
        self.style = style
        self.current_year = datetime.now().year
        self._citation_counter = 0  # For IEEE numbered citations
        self._citation_map = {}     # Maps sources to IEEE numbers
    
    def set_style(self, style: CitationStyle):
        """
        Change the citation style.
        
        Args:
            style: New citation style to use
        """
        self.style = style
        # Reset IEEE counter and map when changing styles
        if style == CitationStyle.IEEE:
            self._citation_counter = 0
            self._citation_map = {}
    
    def reset_state(self):
        """
        Reset the formatter state for a new analysis.
        
        This is essential for IEEE style to ensure numbering starts at [1]
        for each new paper analysis, preventing state leak between analyses.
        """
        self._citation_counter = 0
        self._citation_map = {}
    
    def format_citation(self, source_info: Dict) -> str:
        """
        Format a citation in the selected style.
        
        Args:
            source_info: Dictionary containing source information
            
        Returns:
            Formatted citation
        """
        try:
            # Extract available information
            filename = source_info.get('filename', '')
            metadata = source_info.get('metadata', {})
            
            # Extract common elements
            author = self._extract_author(metadata, filename)
            year = self._extract_year(metadata, filename)
            title = self._extract_title(metadata, filename)
            
            # Format according to selected style
            if self.style == CitationStyle.APA:
                return self._format_apa_citation(author, year, title)
            elif self.style == CitationStyle.MLA:
                return self._format_mla_citation(author, year, title)
            elif self.style == CitationStyle.CHICAGO:
                return self._format_chicago_citation(author, year, title)
            elif self.style == CitationStyle.IEEE:
                return self._format_ieee_citation(author, year, title, filename)
            else:
                return self._format_apa_citation(author, year, title)  # Default to APA
                
        except Exception as e:
            print(f"Error formatting citation: {str(e)}")
            return source_info.get('filename', 'Unknown source')
    
    def format_in_text_citation(self, source_info: Dict, page: Optional[str] = None) -> str:
        """
        Format an in-text citation in the selected style.
        
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
            
            # Format according to selected style
            if self.style == CitationStyle.APA:
                return self._format_apa_in_text(author, year, page)
            elif self.style == CitationStyle.MLA:
                return self._format_mla_in_text(author, year, page)
            elif self.style == CitationStyle.CHICAGO:
                return self._format_chicago_in_text(author, year, page)
            elif self.style == CitationStyle.IEEE:
                return self._format_ieee_in_text(filename, page)
            else:
                return self._format_apa_in_text(author, year, page)  # Default to APA
                
        except Exception as e:
            print(f"Error formatting in-text citation: {str(e)}")
            return "(Unknown, n.d.)"
    
    def format_reference_list(self, citations: List[Dict]) -> str:
        """
        Format a complete reference list in the selected style.
        
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
            
            # Sort and format according to style
            if self.style == CitationStyle.IEEE:
                # IEEE references are numbered in order of appearance (as cited in text)
                # Use the citation_map to maintain consistent numbering
                ordered_references: List[Optional[str]] = [None] * len(references)
                unmapped_refs = []
                
                for citation in citations:
                    source = citation.get('source', '')
                    if source in self._citation_map:
                        ref = self._format_full_reference(citation)
                        if ref:
                            idx = self._citation_map[source] - 1  # Convert to 0-based index
                            if 0 <= idx < len(ordered_references):
                                ordered_references[idx] = ref
                    else:
                        ref = self._format_full_reference(citation)
                        if ref:
                            unmapped_refs.append(ref)
                
                # Add unmapped references at the end
                final_refs = [ref for ref in ordered_references if ref is not None] + unmapped_refs
                
                reference_text = "References\n\n"
                for i, ref in enumerate(final_refs, 1):
                    reference_text += f"[{i}] {ref}\n\n"
            else:
                # Alphabetical sorting for APA, MLA, Chicago
                references.sort()
                
                # Style-specific headers
                if self.style == CitationStyle.MLA:
                    header = "Works Cited\n\n"
                elif self.style == CitationStyle.CHICAGO:
                    header = "Bibliography\n\n"
                else:  # APA and default
                    header = "References\n\n"
                
                reference_text = header
                for ref in references:
                    reference_text += f"{ref}\n\n"
            
            return reference_text.strip()
            
        except Exception as e:
            print(f"Error formatting reference list: {str(e)}")
            return f"{self._get_reference_header()}\n\nError formatting references."
    
    def _format_apa_citation(self, author: str, year: Optional[str], title: str) -> str:
        """Format citation in APA style."""
        if author and year:
            return f"{author} ({year}). {title}."
        elif author:
            return f"{author} (n.d.). {title}."
        elif year:
            return f"{title} ({year})."
        else:
            return f"{title} (n.d.)."
    
    def _format_mla_citation(self, author: str, year: Optional[str], title: str) -> str:
        """Format citation in MLA style."""
        if author:
            # MLA: Author. "Title." Year.
            formatted_title = f'"{title}"' if not title.startswith('"') else title
            if year:
                return f"{author}. {formatted_title} {year}."
            else:
                return f"{author}. {formatted_title}"
        else:
            # Title-first when no author
            formatted_title = f'"{title}"' if not title.startswith('"') else title
            if year:
                return f"{formatted_title} {year}."
            else:
                return f"{formatted_title}"
    
    def _format_chicago_citation(self, author: str, year: Optional[str], title: str) -> str:
        """Format citation in Chicago Author-Date style."""
        if author and year:
            return f"{author}. {year}. \"{title}\"."
        elif author:
            return f"{author}. n.d. \"{title}\"."
        elif year:
            return f"\"{title}\". {year}."
        else:
            return f"\"{title}\". n.d."
    
    def _format_ieee_citation(self, author: str, year: Optional[str], title: str, filename: str) -> str:
        """Format citation in IEEE style."""
        formatted_title = f'"{title}"' if not title.startswith('"') else title
        
        if author and year:
            return f"{author}, {formatted_title} {year}."
        elif author:
            return f"{author}, {formatted_title}"
        elif year:
            return f"{formatted_title} {year}."
        else:
            return f"{formatted_title}"
    
    def _format_apa_in_text(self, author: str, year: Optional[str], page: Optional[str]) -> str:
        """Format APA in-text citation."""
        if author and year:
            base_citation = f"({author}, {year}"
        elif author:
            base_citation = f"({author}, n.d."
        else:
            base_citation = f"(Unknown, n.d."
        
        if page:
            return f"{base_citation}, p. {page})"
        else:
            return f"{base_citation})"
    
    def _format_mla_in_text(self, author: str, year: Optional[str], page: Optional[str]) -> str:
        """Format MLA in-text citation."""
        if author:
            if page:
                return f"({author} {page})"
            else:
                return f"({author})"
        else:
            if page:
                return f"(Unknown {page})"
            else:
                return f"(Unknown)"
    
    def _format_chicago_in_text(self, author: str, year: Optional[str], page: Optional[str]) -> str:
        """Format Chicago Author-Date in-text citation."""
        if author and year:
            base_citation = f"({author} {year}"
        elif author:
            base_citation = f"({author} n.d."
        else:
            base_citation = f"(Unknown n.d."
        
        if page:
            return f"{base_citation}, {page})"
        else:
            return f"{base_citation})"
    
    def _format_ieee_in_text(self, filename: str, page: Optional[str]) -> str:
        """Format IEEE in-text citation."""
        # Get or assign number for this source
        if filename not in self._citation_map:
            self._citation_counter += 1
            self._citation_map[filename] = self._citation_counter
        
        number = self._citation_map[filename]
        
        if page:
            return f"[{number}, p. {page}]"
        else:
            return f"[{number}]"
    
    def _format_full_reference(self, citation: Dict) -> Optional[str]:
        """
        Format a full reference entry using available metadata.
        
        Args:
            citation: Citation dictionary with potential metadata
            
        Returns:
            Formatted reference or None
        """
        try:
            metadata = citation.get('metadata', {})
            filename = citation.get('source', '')
            
            author = self._extract_author(metadata, filename)
            year = self._extract_year(metadata, filename)
            title = self._extract_title(metadata, filename)
            
            # Format according to selected style
            if self.style == CitationStyle.APA:
                return self._format_apa_full_reference(author, year, title, metadata)
            elif self.style == CitationStyle.MLA:
                return self._format_mla_full_reference(author, year, title, metadata)
            elif self.style == CitationStyle.CHICAGO:
                return self._format_chicago_full_reference(author, year, title, metadata)
            elif self.style == CitationStyle.IEEE:
                return self._format_ieee_full_reference(author, year, title, metadata)
            else:
                return self._format_apa_full_reference(author, year, title, metadata)
                
        except Exception as e:
            print(f"Error formatting full reference: {str(e)}")
            return None
    
    def _format_apa_full_reference(self, author: str, year: Optional[str], title: str, metadata: Optional[Dict] = None) -> Optional[str]:
        """Format APA full reference with enhanced academic fields."""
        if metadata is None:
            metadata = {}
        
        if not title:
            return None
        
        # Build reference parts
        parts = []
        
        # Author and year
        if author and year:
            parts.append(f"{author} ({year}).")
        elif author:
            parts.append(f"{author} (n.d.).")
        elif year:
            parts.append(f"{title} ({year}).")
        else:
            parts.append(f"{title} (n.d.).")
            return " ".join(parts)
        
        # Title (if author exists)
        if author:
            parts.append(f"{title}.")
        
        # Journal information
        journal = metadata.get('journal', metadata.get('subject', ''))
        volume = metadata.get('volume', '')
        issue = metadata.get('issue', '')
        pages = metadata.get('pages', '')
        
        if journal:
            journal_part = f"*{journal}*"
            if volume and issue:
                journal_part += f", {volume}({issue})"
            elif volume:
                journal_part += f", {volume}"
            if pages:
                journal_part += f", {pages}"
            parts.append(f"{journal_part}.")
        
        # Publisher (for books)
        publisher = metadata.get('publisher', '')
        if publisher and not journal:
            parts.append(f"{publisher}.")
        
        # DOI or URL
        doi = metadata.get('doi', '')
        url = metadata.get('url', '')
        if doi:
            parts.append(f"https://doi.org/{doi}")
        elif url:
            parts.append(url)
        
        return " ".join(parts)
    
    def _format_mla_full_reference(self, author: str, year: Optional[str], title: str, metadata: Optional[Dict] = None) -> Optional[str]:
        """Format MLA full reference with enhanced academic fields."""
        if metadata is None:
            metadata = {}
        
        if not title:
            return None
        
        formatted_title = f'"{title}"' if not title.startswith('"') else title
        
        parts = []
        
        # Author and title
        if author:
            parts.append(f"{author}.")
        parts.append(formatted_title)
        
        # Journal information
        journal = metadata.get('journal', metadata.get('subject', ''))
        volume = metadata.get('volume', '')
        issue = metadata.get('issue', '')
        pages = metadata.get('pages', '')
        
        if journal:
            parts.append(f"*{journal}*,")
            if volume and issue:
                parts.append(f"vol. {volume}, no. {issue},")
            elif volume:
                parts.append(f"vol. {volume},")
        
        # Year
        if year:
            parts.append(f"{year},")
        
        # Pages
        if pages:
            if journal:
                parts.append(f"pp. {pages}.")
            else:
                parts.append(f"{pages}.")
        else:
            # Remove trailing comma if no pages
            if parts and parts[-1].endswith(','):
                parts[-1] = parts[-1].rstrip(',') + '.'
        
        # Publisher (for books)
        publisher = metadata.get('publisher', '')
        if publisher and not journal:
            parts.insert(-1, f"{publisher},") if year else parts.append(f"{publisher}.")
        
        # DOI or URL
        doi = metadata.get('doi', '')
        url = metadata.get('url', '')
        if doi:
            parts.append(f"DOI: {doi}.")
        elif url:
            parts.append(f"Web. {url}.")
        
        return " ".join(parts)
    
    def _format_chicago_full_reference(self, author: str, year: Optional[str], title: str, metadata: Optional[Dict] = None) -> Optional[str]:
        """Format Chicago full reference with enhanced academic fields."""
        if metadata is None:
            metadata = {}
        
        if not title:
            return None
        
        formatted_title = f'"{title}"' if not title.startswith('"') else title
        
        parts = []
        
        # Author and year
        if author and year:
            parts.append(f"{author}. {year}.")
        elif author:
            parts.append(f"{author}. n.d.")
        elif year:
            parts.append(f"{formatted_title} {year}.")
            return " ".join(parts)
        else:
            parts.append(f"{formatted_title} n.d.")
            return " ".join(parts)
        
        # Title (if author exists)
        if author:
            parts.append(formatted_title)
        
        # Journal information
        journal = metadata.get('journal', metadata.get('subject', ''))
        volume = metadata.get('volume', '')
        issue = metadata.get('issue', '')
        pages = metadata.get('pages', '')
        
        if journal:
            journal_part = f"*{journal}*"
            if volume and issue:
                journal_part += f" {volume}, no. {issue}"
            elif volume:
                journal_part += f" {volume}"
            if pages:
                journal_part += f" ({year}): {pages}." if year else f": {pages}."
            else:
                journal_part += f" ({year})." if year else "."
            parts.append(journal_part)
        
        # Publisher (for books)
        publisher = metadata.get('publisher', '')
        if publisher and not journal:
            parts.append(f"{publisher}.")
        elif not journal:
            parts.append(".")
        
        # DOI or URL
        doi = metadata.get('doi', '')
        url = metadata.get('url', '')
        if doi:
            parts.append(f"doi:{doi}.")
        elif url:
            parts.append(f"Accessed via {url}.")
        
        return " ".join(parts)
    
    def _format_ieee_full_reference(self, author: str, year: Optional[str], title: str, metadata: Optional[Dict] = None) -> Optional[str]:
        """Format IEEE full reference with enhanced academic fields."""
        if metadata is None:
            metadata = {}
        
        if not title:
            return None
        
        formatted_title = f'"{title}"' if not title.startswith('"') else title
        
        parts = []
        
        # Author
        if author:
            parts.append(f"{author},")
        
        # Title
        parts.append(formatted_title)
        
        # Journal information
        journal = metadata.get('journal', metadata.get('subject', ''))
        volume = metadata.get('volume', '')
        issue = metadata.get('issue', '')
        pages = metadata.get('pages', '')
        
        if journal:
            journal_part = f"*{journal}*"
            if volume and issue:
                journal_part += f", vol. {volume}, no. {issue}"
            elif volume:
                journal_part += f", vol. {volume}"
            if pages:
                journal_part += f", pp. {pages}"
            if year:
                journal_part += f", {year}."
            else:
                journal_part += "."
            parts.append(journal_part)
        
        # Publisher and year (for books)
        elif not journal:
            publisher = metadata.get('publisher', '')
            if publisher and year:
                parts.append(f"{publisher}, {year}.")
            elif year:
                parts.append(f"{year}.")
            elif publisher:
                parts.append(f"{publisher}.")
            else:
                parts.append(".")
        
        # DOI or URL
        doi = metadata.get('doi', '')
        url = metadata.get('url', '')
        if doi:
            parts.append(f"DOI: {doi}")
        elif url:
            parts.append(f"[Online]. Available: {url}")
        
        return " ".join(parts)
    
    def _get_reference_header(self) -> str:
        """Get the appropriate reference header for the current style."""
        if self.style == CitationStyle.MLA:
            return "Works Cited"
        elif self.style == CitationStyle.CHICAGO:
            return "Bibliography"
        else:  # APA, IEEE, and default
            return "References"
    
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
        # Try enhanced metadata first (from bibliography parser)
        authors_list = metadata.get('authors', [])
        if authors_list and isinstance(authors_list, list):
            if short_form:
                # For in-text citations, use first author's last name for most styles
                if self.style == CitationStyle.IEEE:
                    return ', '.join(authors_list)
                first_author = authors_list[0]
                parts = first_author.split()
                if parts:
                    return parts[-1]  # Last name
            # Join multiple authors properly
            if len(authors_list) == 1:
                return authors_list[0]
            elif len(authors_list) == 2:
                return f"{authors_list[0]} and {authors_list[1]}"
            else:
                return f"{authors_list[0]} et al."
        
        # Fallback to single author field
        author = metadata.get('author', '').strip()
        if author:
            if short_form:
                # For in-text citations, use last name only for most styles
                # Exception: IEEE uses numbers, so we don't need short form
                if self.style == CitationStyle.IEEE:
                    return author
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
                if short_form and self.style != CitationStyle.IEEE:
                    parts = author.split()
                    if parts:
                        return parts[-1]
                return author
        
        # Default fallback - return empty string for proper title-first formatting
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
        # Try enhanced metadata first (from bibliography parser)
        year = metadata.get('year', '').strip()
        if year:
            try:
                year_int = int(year)
                if 1900 <= year_int <= self.current_year:
                    return str(year_int)
            except ValueError:
                pass
        
        # Try creation date from PDF metadata
        creation_date = metadata.get('creation_date', '')
        if creation_date:
            year_match = re.search(r'(\d{4})', str(creation_date))
            if year_match:
                year_int = int(year_match.group(1))
                if 1900 <= year_int <= self.current_year:
                    return str(year_int)
        
        # Try filename
        year_matches = re.findall(r'(\d{4})', filename)
        for year_str in year_matches:
            year_int = int(year_str)
            if 1900 <= year_int <= self.current_year:
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
        Validate if a citation follows the current style format.
        
        Args:
            citation: Citation string to validate
            
        Returns:
            True if valid format
        """
        try:
            if self.style == CitationStyle.APA:
                return self._validate_apa_format(citation)
            elif self.style == CitationStyle.MLA:
                return self._validate_mla_format(citation)
            elif self.style == CitationStyle.CHICAGO:
                return self._validate_chicago_format(citation)
            elif self.style == CitationStyle.IEEE:
                return self._validate_ieee_format(citation)
            else:
                return self._validate_apa_format(citation)  # Default to APA
                
        except Exception:
            return False
    
    def _validate_apa_format(self, citation: str) -> bool:
        """Validate APA format."""
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
    
    def _validate_mla_format(self, citation: str) -> bool:
        """Validate MLA format."""
        patterns = [
            r'^.+\.\s*".+"\s*\d{4}\..*',  # Author. "Title" Year.
            r'^\(.+\s+\d+\)',              # (Author Page)
        ]
        
        for pattern in patterns:
            if re.match(pattern, citation):
                return True
        return False
    
    def _validate_chicago_format(self, citation: str) -> bool:
        """Validate Chicago format."""
        patterns = [
            r'^.+\.\s*\d{4}\.\s*".+"\..*',  # Author. Year. "Title".
            r'^\(.+\s+\d{4}\)',              # (Author Year)
        ]
        
        for pattern in patterns:
            if re.match(pattern, citation):
                return True
        return False
    
    def _validate_ieee_format(self, citation: str) -> bool:
        """Validate IEEE format."""
        patterns = [
            r'^\[\d+\]',                     # [Number]
            r'^.+,\s*".+".*',               # Author, "Title"
        ]
        
        for pattern in patterns:
            if re.match(pattern, citation):
                return True
        return False
    
    def get_citation_suggestions(self, text: str) -> List[str]:
        """
        Get suggestions for improving citation format based on current style.
        
        Args:
            text: Text to analyze
            
        Returns:
            List of suggestions
        """
        suggestions = []
        
        if self.style == CitationStyle.APA:
            suggestions.extend(self._get_apa_suggestions(text))
        elif self.style == CitationStyle.MLA:
            suggestions.extend(self._get_mla_suggestions(text))
        elif self.style == CitationStyle.CHICAGO:
            suggestions.extend(self._get_chicago_suggestions(text))
        elif self.style == CitationStyle.IEEE:
            suggestions.extend(self._get_ieee_suggestions(text))
        
        return suggestions
    
    def _get_apa_suggestions(self, text: str) -> List[str]:
        """Get APA-specific suggestions."""
        suggestions = []
        
        if re.search(r'\d{4}', text) and not re.search(r'\(\d{4}\)', text):
            suggestions.append("Consider formatting years in parentheses: (2023)")
        
        if '&' in text:
            suggestions.append("Use 'and' instead of '&' in narrative citations")
        
        if re.search(r'pp?\.\s*\d+', text, re.IGNORECASE):
            suggestions.append("Page references should use 'p.' for single pages, 'pp.' for ranges")
        
        return suggestions
    
    def _get_mla_suggestions(self, text: str) -> List[str]:
        """Get MLA-specific suggestions."""
        suggestions = []
        
        if '(' in text and ',' in text:
            suggestions.append("MLA in-text citations use (Author Page) format, no comma")
        
        if '"' not in text and 'title' in text.lower():
            suggestions.append("Titles should be in quotation marks for MLA style")
        
        return suggestions
    
    def _get_chicago_suggestions(self, text: str) -> List[str]:
        """Get Chicago-specific suggestions."""
        suggestions = []
        
        if re.search(r'\(\w+,\s*\d{4}\)', text):
            suggestions.append("Chicago Author-Date uses (Author Year) format, no comma")
        
        return suggestions
    
    def _get_ieee_suggestions(self, text: str) -> List[str]:
        """Get IEEE-specific suggestions."""
        suggestions = []
        
        if '(' in text and ')' in text and not re.search(r'\[\d+\]', text):
            suggestions.append("IEEE citations use numbered format: [1]")
        
        return suggestions

    def get_available_styles(self) -> List[str]:
        """
        Get list of available citation styles.
        
        Returns:
            List of citation style names
        """
        return [style.value for style in CitationStyle]
    
    def get_current_style(self) -> str:
        """
        Get the current citation style name.
        
        Returns:
            Current style name
        """
        return self.style.value

# Backwards compatibility - create an alias for the old APA formatter
APAFormatter = lambda: CitationFormatter(CitationStyle.APA)