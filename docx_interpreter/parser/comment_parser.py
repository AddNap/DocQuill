"""
Comment parser for DOCX documents.

Implements comment parsing functionality including comment content parsing,
comment author parsing, comment date parsing, and comment range parsing.
"""

import xml.etree.ElementTree as ET
from typing import List, Dict, Optional, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class CommentParser:
    """
    Parser for comments and annotations.
    
    Provides functionality for:
    - Comment content parsing
    - Comment metadata parsing (author, date, etc.)
    - Comment range parsing
    - Comment validation
    """
    
    def __init__(self, package_reader, xml_mapper):
        """
        Initialize comment parser.
        
        Args:
            package_reader: Package reader instance
            xml_mapper: XML mapper instance
        """
        self.package_reader = package_reader
        self.xml_mapper = xml_mapper
        self.ns = {
            'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
        }
        self.comments: Dict[str, Dict[str, Any]] = {}
    
    def parse_comments(self) -> Dict[str, Dict[str, Any]]:
        """
        Parse comments from comments.xml.
        
        Returns:
            Dictionary of comments with their metadata
        """
        try:
            # Try to get comments.xml content
            comments_content = self.package_reader.get_part_content('word/comments.xml')
            if not comments_content:
                logger.debug("No comments.xml found")
                return {}
            
            # Parse comments XML
            comments_root = ET.fromstring(comments_content)
            
            # Find all comment elements
            comment_elements = comments_root.findall('.//w:comment', self.ns)
            
            for comment_element in comment_elements:
                comment_data = self.parse_comment(comment_element)
                if comment_data:
                    self.comments[comment_data['id']] = comment_data
            
            logger.info(f"Parsed {len(self.comments)} comments")
            return self.comments
            
        except Exception as e:
            logger.error(f"Failed to parse comments: {e}")
            return {}
    
    def parse_comment(self, comment_element) -> Optional[Dict[str, Any]]:
        """
        Parse individual comment.
        
        Args:
            comment_element: XML element containing comment
            
        Returns:
            Dictionary with comment data or None if parsing failed
        """
        try:
            # Get comment ID
            comment_id = comment_element.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}id')
            if not comment_id:
                logger.warning("Comment missing ID")
                return None
            
            # Get comment author
            author_element = comment_element.find('.//w:author', self.ns)
            author = author_element.text if author_element is not None else ''
            
            # Get comment date
            date_element = comment_element.find('.//w:date', self.ns)
            date_str = date_element.text if date_element is not None else ''
            
            # Parse date if available
            comment_date = None
            if date_str:
                try:
                    # Try to parse ISO format date
                    comment_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                except ValueError:
                    try:
                        # Try alternative format
                        comment_date = datetime.strptime(date_str, '%Y-%m-%dT%H:%M:%S')
                    except ValueError:
                        logger.warning(f"Could not parse comment date: {date_str}")
            
            # Get comment content
            content_elements = comment_element.findall('.//w:p', self.ns)
            content = []
            
            for para_element in content_elements:
                para_text = self._extract_paragraph_text(para_element)
                if para_text:
                    content.append(para_text)
            
            # Get comment initials
            initials_element = comment_element.find('.//w:initials', self.ns)
            initials = initials_element.text if initials_element is not None else ''
            
            comment_data = {
                'id': comment_id,
                'author': author,
                'initials': initials,
                'date': comment_date,
                'date_string': date_str,
                'content': content,
                'content_text': '\n'.join(content),
                'paragraph_count': len(content)
            }
            
            return comment_data
            
        except Exception as e:
            logger.error(f"Failed to parse comment: {e}")
            return None
    
    def parse_comment_range(self, range_element) -> Optional[Dict[str, Any]]:
        """
        Parse comment range.
        
        Args:
            range_element: XML element containing comment range
            
        Returns:
            Dictionary with range data or None if parsing failed
        """
        try:
            # Get comment reference
            comment_ref = range_element.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}id')
            if not comment_ref:
                logger.warning("Comment range missing reference")
                return None
            
            # Get range start
            start_element = range_element.find('.//w:commentRangeStart', self.ns)
            start_pos = start_element.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}id') if start_element is not None else None
            
            # Get range end
            end_element = range_element.find('.//w:commentRangeEnd', self.ns)
            end_pos = end_element.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}id') if end_element is not None else None
            
            # Get range text
            range_text = self._extract_range_text(range_element)
            
            range_data = {
                'comment_ref': comment_ref,
                'start_pos': start_pos,
                'end_pos': end_pos,
                'text': range_text,
                'text_length': len(range_text) if range_text else 0
            }
            
            return range_data
            
        except Exception as e:
            logger.error(f"Failed to parse comment range: {e}")
            return None
    
    def _extract_paragraph_text(self, para_element) -> str:
        """
        Extract text from paragraph element.
        
        Args:
            para_element: Paragraph XML element
            
        Returns:
            Extracted text
        """
        try:
            text_parts = []
            
            # Find all text elements
            text_elements = para_element.findall('.//w:t', self.ns)
            for text_element in text_elements:
                if text_element.text:
                    text_parts.append(text_element.text)
            
            return ''.join(text_parts)
            
        except Exception as e:
            logger.error(f"Failed to extract paragraph text: {e}")
            return ''
    
    def _extract_range_text(self, range_element) -> str:
        """
        Extract text from comment range element.
        
        Args:
            range_element: Range XML element
            
        Returns:
            Extracted text
        """
        try:
            text_parts = []
            
            # Find all text elements in range
            text_elements = range_element.findall('.//w:t', self.ns)
            for text_element in text_elements:
                if text_element.text:
                    text_parts.append(text_element.text)
            
            return ''.join(text_parts)
            
        except Exception as e:
            logger.error(f"Failed to extract range text: {e}")
            return ''
    
    def get_comment_by_id(self, comment_id: str) -> Optional[Dict[str, Any]]:
        """
        Get comment by ID.
        
        Args:
            comment_id: Comment identifier
            
        Returns:
            Comment data or None if not found
        """
        return self.comments.get(comment_id)
    
    def get_comments_by_author(self, author: str) -> List[Dict[str, Any]]:
        """
        Get comments by author.
        
        Args:
            author: Author name
            
        Returns:
            List of comments by the author
        """
        return [comment for comment in self.comments.values() if comment.get('author') == author]
    
    def get_comments_by_date_range(self, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        """
        Get comments within date range.
        
        Args:
            start_date: Start date
            end_date: End date
            
        Returns:
            List of comments within date range
        """
        comments_in_range = []
        
        for comment in self.comments.values():
            comment_date = comment.get('date')
            if comment_date and start_date <= comment_date <= end_date:
                comments_in_range.append(comment)
        
        return comments_in_range
    
    def get_comment_stats(self) -> Dict[str, Any]:
        """
        Get comment statistics.
        
        Returns:
            Dictionary with comment statistics
        """
        if not self.comments:
            return {'total_comments': 0}
        
        authors = set(comment.get('author', '') for comment in self.comments.values())
        total_content_length = sum(len(comment.get('content_text', '')) for comment in self.comments.values())
        
        return {
            'total_comments': len(self.comments),
            'unique_authors': len(authors),
            'total_content_length': total_content_length,
            'average_content_length': total_content_length / len(self.comments) if self.comments else 0,
            'authors': list(authors)
        }
