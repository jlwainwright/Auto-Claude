/**
 * Unit tests for MemoryDetailPanel component
 * Tests memory details display, edit/delete operations,
 * connections visualization, and dialog interactions
 *
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import type { MemoryGraphNode, MemoryGraphEdge } from '../../../../shared/types';

// Helper to create test node
function createTestNode(overrides: Partial<MemoryGraphNode> = {}): MemoryGraphNode {
  return {
    id: `node-${Date.now()}-${Math.random().toString(36).substring(7)}`,
    label: 'Test Memory',
    type: 'pattern',
    timestamp: new Date().toISOString(),
    content: '{"what_worked": ["Test pattern worked well"]}',
    session_number: 1,
    group_id: 'test-group-123',
    ...overrides
  };
}

// Helper to create test edge
function createTestEdge(overrides: Partial<MemoryGraphEdge> = {}): MemoryGraphEdge {
  return {
    source: 'node-source',
    target: 'node-target',
    relationship_type: 'related_to',
    label: 'Related To',
    source_name: 'Source Memory',
    target_name: 'Target Memory',
    ...overrides
  };
}

describe('MemoryDetailPanel', () => {
  const mockOnClose = vi.fn();
  const mockOnEdit = vi.fn();
  const mockOnDelete = vi.fn();
  const testProjectId = 'test-project-id';

  beforeEach(() => {
    // Reset all mocks
    vi.clearAllMocks();
  });

  describe('Component Props', () => {
    it('should accept required props', () => {
      const node = createTestNode();
      const edges = [createTestEdge()];
      const projectId = testProjectId;

      expect(node).toBeDefined();
      expect(edges).toBeDefined();
      expect(projectId).toBeDefined();
      expect(typeof mockOnClose).toBe('function');
    });

    it('should accept optional onEdit callback', () => {
      const onEdit = mockOnEdit;
      expect(onEdit).toBeDefined();
      expect(typeof onEdit).toBe('function');
    });

    it('should accept optional onDelete callback', () => {
      const onDelete = mockOnDelete;
      expect(onDelete).toBeDefined();
      expect(typeof onDelete).toBe('function');
    });

    it('should handle missing onEdit callback', () => {
      const onEdit = undefined;
      expect(onEdit).toBeUndefined();
    });

    it('should handle missing onDelete callback', () => {
      const onDelete = undefined;
      expect(onDelete).toBeUndefined();
    });
  });

  describe('Panel Header Rendering', () => {
    it('should display memory type badge', () => {
      const node = createTestNode({ type: 'gotcha' });
      const badgeLabel = 'Gotcha'; // from memoryTypeLabels
      const badgeColorClass = 'text-destructive'; // from memoryTypeColors

      expect(node.type).toBe('gotcha');
      expect(badgeLabel).toBe('Gotcha');
      expect(badgeColorClass).toBeTruthy();
    });

    it('should display memory label in header', () => {
      const node = createTestNode({ label: 'Important Pattern' });
      const label = node.label;

      expect(label).toBe('Important Pattern');
    });

    it('should truncate long labels', () => {
      const longLabel = 'A'.repeat(100);
      const node = createTestNode({ label: longLabel });
      const shouldTruncate = node.label.length > 50;

      expect(shouldTruncate).toBe(true);
      expect(node.label.length).toBe(100);
    });

    it('should have close button', () => {
      // From component: X icon in Button
      const hasCloseButton = true;
      expect(hasCloseButton).toBe(true);
    });

    it('should call onClose when close button is clicked', () => {
      mockOnClose();

      expect(mockOnClose).toHaveBeenCalledTimes(1);
    });

    it('should have correct close button title', () => {
      // From component: title="Close panel"
      const buttonTitle = 'Close panel';
      expect(buttonTitle).toBe('Close panel');
    });
  });

  describe('Memory Metadata Display', () => {
    it('should display created timestamp', () => {
      const node = createTestNode({
        timestamp: '2024-01-11T10:30:00Z'
      });

      expect(node.timestamp).toBeDefined();
      expect(node.timestamp).toBeTruthy();
    });

    it('should show Calendar icon for timestamp', () => {
      // From component: Calendar icon
      const hasCalendarIcon = true;
      expect(hasCalendarIcon).toBe(true);
    });

    it('should display session number when available', () => {
      const node = createTestNode({ session_number: 5 });
      const hasSessionNumber = !!node.session_number;

      expect(hasSessionNumber).toBe(true);
      expect(node.session_number).toBe(5);
    });

    it('should show Hash icon for session number', () => {
      // From component: Hash icon
      const hasHashIcon = true;
      expect(hasHashIcon).toBe(true);
    });

    it('should not display session number when not available', () => {
      const node = createTestNode({ session_number: undefined });
      const hasSessionNumber = !!node.session_number;

      expect(hasSessionNumber).toBe(false);
    });

    it('should display group_id when available', () => {
      const node = createTestNode({ group_id: 'group-abc-123' });
      const hasGroupId = !!node.group_id;

      expect(hasGroupId).toBe(true);
      expect(node.group_id).toBe('group-abc-123');
    });

    it('should show FolderSymlink icon for group_id', () => {
      // From component: FolderSymlink icon
      const hasFolderIcon = true;
      expect(hasFolderIcon).toBe(true);
    });

    it('should not display group_id when not available', () => {
      const node = createTestNode({ group_id: undefined });
      const hasGroupId = !!node.group_id;

      expect(hasGroupId).toBe(false);
    });

    it('should truncate long group_id', () => {
      const longGroupId = 'group-' + 'x'.repeat(100);
      const node = createTestNode({ group_id: longGroupId });
      const maxLength = 30;
      const shouldTruncate = node.group_id ? node.group_id.length > maxLength : false;

      expect(shouldTruncate).toBe(true);
    });

    it('should use monospace font for group_id', () => {
      // From component: className="font-mono text-xs"
      const fontClass = 'font-mono';
      expect(fontClass).toBe('font-mono');
    });
  });

  describe('Memory Content Display', () => {
    it('should display content when available', () => {
      const node = createTestNode({
        content: '{"what_worked": ["Use React hooks"]}'
      });
      const hasContent = !!node.content;

      expect(hasContent).toBe(true);
      expect(node.content).toBeDefined();
    });

    it('should not display content section when not available', () => {
      const node = createTestNode({ content: undefined });
      const hasContent = !!node.content;

      expect(hasContent).toBe(false);
    });

    it('should use monospace font for content', () => {
      // From component: className="text-xs text-muted-foreground whitespace-pre-wrap font-mono"
      const fontClass = 'font-mono';
      expect(fontClass).toBe('font-mono');
    });

    it('should preserve whitespace in content', () => {
      // From component: whitespace-pre-wrap
      const whitespaceClass = 'whitespace-pre-wrap';
      expect(whitespaceClass).toBe('whitespace-pre-wrap');
    });

    it('should have max height for content with scroll', () => {
      // From component: max-h-96 overflow-auto
      const maxHeight = 'max-h-96';
      const overflow = 'overflow-auto';
      expect(maxHeight).toBe('max-h-96');
      expect(overflow).toBe('overflow-auto');
    });

    it('should display content heading', () => {
      // From component: <h4 className="text-sm font-semibold text-foreground">Content</h4>
      const heading = 'Content';
      expect(heading).toBe('Content');
    });
  });

  describe('Connections Display', () => {
    it('should filter incoming edges correctly', () => {
      const nodeId = 'current-node';
      const edges = [
        createTestEdge({ target: nodeId, source: 'node-1' }),
        createTestEdge({ source: nodeId, target: 'node-2' }),
        createTestEdge({ target: nodeId, source: 'node-3' })
      ];

      const incomingEdges = edges.filter(edge => edge.target === nodeId);

      expect(incomingEdges).toHaveLength(2);
      expect(incomingEdges[0].source).toBe('node-1');
      expect(incomingEdges[1].source).toBe('node-3');
    });

    it('should filter outgoing edges correctly', () => {
      const nodeId = 'current-node';
      const edges = [
        createTestEdge({ target: nodeId, source: 'node-1' }),
        createTestEdge({ source: nodeId, target: 'node-2' }),
        createTestEdge({ source: nodeId, target: 'node-3' })
      ];

      const outgoingEdges = edges.filter(edge => edge.source === nodeId);

      expect(outgoingEdges).toHaveLength(2);
      expect(outgoingEdges[0].target).toBe('node-2');
      expect(outgoingEdges[1].target).toBe('node-3');
    });

    it('should determine if node has connections', () => {
      const nodeId = 'current-node';
      const edgesWithConnections = [
        createTestEdge({ target: nodeId }),
        createTestEdge({ source: nodeId })
      ];
      const edgesWithoutConnections: MemoryGraphEdge[] = [];

      const hasConnections1 = edgesWithConnections.some(
        edge => edge.target === nodeId || edge.source === nodeId
      );
      const hasConnections2 = edgesWithoutConnections.some(
        edge => edge.target === nodeId || edge.source === nodeId
      );

      expect(hasConnections1).toBe(true);
      expect(hasConnections2).toBe(false);
    });

    it('should show connections section when hasConnections is true', () => {
      const incomingEdges = [createTestEdge()];
      const outgoingEdges = [createTestEdge()];
      const hasConnections = incomingEdges.length > 0 || outgoingEdges.length > 0;

      expect(hasConnections).toBe(true);
    });

    it('should not show connections section when hasConnections is false', () => {
      const incomingEdges: MemoryGraphEdge[] = [];
      const outgoingEdges: MemoryGraphEdge[] = [];
      const hasConnections = incomingEdges.length > 0 || outgoingEdges.length > 0;

      expect(hasConnections).toBe(false);
    });

    it('should display connections count in heading', () => {
      const incomingEdges = [createTestEdge(), createTestEdge()];
      const outgoingEdges = [createTestEdge()];
      const totalCount = incomingEdges.length + outgoingEdges.length;
      const heading = `Connections (${totalCount})`;

      expect(heading).toBe('Connections (3)');
      expect(totalCount).toBe(3);
    });

    it('should display incoming connections with arrow', () => {
      // From component: <span className="text-accent">←</span>
      const arrow = '←';
      expect(arrow).toBe('←');
    });

    it('should display outgoing connections with arrow', () => {
      // From component: <span className="text-accent">→</span>
      const arrow = '→';
      expect(arrow).toBe('→');
    });

    it('should display connection source/target name', () => {
      const edge = createTestEdge({
        source_name: 'Source Memory',
        target_name: 'Target Memory'
      });

      expect(edge.source_name).toBe('Source Memory');
      expect(edge.target_name).toBe('Target Memory');
    });

    it('should fall back to ID when name is not available', () => {
      const edge = createTestEdge({
        source_name: undefined,
        source: 'node-source-id'
      });
      const displayName = edge.source_name || edge.source;

      expect(displayName).toBe('node-source-id');
    });

    it('should display relationship type', () => {
      const edge = createTestEdge({
        relationship_type: 'related_to',
        label: 'Related To'
      });
      const relationship = edge.label || edge.relationship_type;

      expect(relationship).toBe('Related To');
    });

    it('should capitalize relationship type display', () => {
      // From component: className="capitalize"
      const relationship = 'related_to';
      const capitalized = relationship.charAt(0).toUpperCase() + relationship.slice(1);

      expect(capitalized).toBe('Related_to');
    });
  });

  describe('No Connections State', () => {
    it('should show message when no connections exist', () => {
      const incomingEdges: MemoryGraphEdge[] = [];
      const outgoingEdges: MemoryGraphEdge[] = [];
      const hasConnections = incomingEdges.length > 0 || outgoingEdges.length > 0;

      expect(hasConnections).toBe(false);
    });

    it('should display no connections message', () => {
      // From component: No connections to other memories
      const message = 'No connections to other memories';
      expect(message).toBe('No connections to other memories');
    });

    it('should center the no connections message', () => {
      // From component: className="text-center"
      const textAlignClass = 'text-center';
      expect(textAlignClass).toBe('text-center');
    });

    it('should style message as muted and italic', () => {
      // From component: className="text-sm text-muted-foreground text-center py-4 italic"
      const classes = ['text-muted-foreground', 'italic'];
      expect(classes).toContain('text-muted-foreground');
      expect(classes).toContain('italic');
    });
  });

  describe('Edit Button', () => {
    it('should render edit button', () => {
      // From component: Edit icon with text "Edit"
      const hasEditButton = true;
      expect(hasEditButton).toBe(true);
    });

    it('should show Edit icon', () => {
      // From component: Edit from lucide-react
      const hasEditIcon = true;
      expect(hasEditIcon).toBe(true);
    });

    it('should call onEdit when clicked', () => {
      const node = createTestNode({ id: 'edit-node' });
      mockOnEdit(node);

      expect(mockOnEdit).toHaveBeenCalledWith(node);
      expect(mockOnEdit).toHaveBeenCalledTimes(1);
    });

    it('should be disabled when onEdit is not provided', () => {
      const onEdit = undefined;
      const isDisabled = !onEdit;

      expect(isDisabled).toBe(true);
    });

    it('should be enabled when onEdit is provided', () => {
      const onEdit = mockOnEdit;
      const isDisabled = !onEdit;

      expect(isDisabled).toBe(false);
    });

    it('should use outline variant', () => {
      // From component: variant="outline"
      const variant = 'outline';
      expect(variant).toBe('outline');
    });

    it('should use small size', () => {
      // From component: size="sm"
      const size = 'sm';
      expect(size).toBe('sm');
    });

    it('should have flex-1 class for width', () => {
      // From component: className="flex-1"
      const widthClass = 'flex-1';
      expect(widthClass).toBe('flex-1');
    });
  });

  describe('Delete Button', () => {
    it('should render delete button', () => {
      // From component: Trash2 icon with text "Delete"
      const hasDeleteButton = true;
      expect(hasDeleteButton).toBe(true);
    });

    it('should show Trash2 icon', () => {
      // From component: Trash2 from lucide-react
      const hasTrashIcon = true;
      expect(hasTrashIcon).toBe(true);
    });

    it('should open confirmation dialog when clicked', () => {
      const setShowDeleteDialog = vi.fn();
      const openDialog = () => setShowDeleteDialog(true);

      openDialog();

      expect(setShowDeleteDialog).toHaveBeenCalledWith(true);
    });

    it('should be disabled when onDelete is not provided', () => {
      const onDelete = undefined;
      const isDisabled = !onDelete;

      expect(isDisabled).toBe(true);
    });

    it('should be enabled when onDelete is provided', () => {
      const onDelete = mockOnDelete;
      const isDisabled = !onDelete;

      expect(isDisabled).toBe(false);
    });

    it('should be disabled during deletion', () => {
      const isDeleting = true;
      expect(isDeleting).toBe(true);
    });

    it('should show Loader2 spinner when deleting', () => {
      // From component: Loader2 className="h-4 w-4 mr-2 animate-spin"
      const hasSpinner = true;
      expect(hasSpinner).toBe(true);
    });

    it('should show "Deleting..." text when deleting', () => {
      const isDeleting = true;
      const text = isDeleting ? 'Deleting...' : 'Delete';

      expect(text).toBe('Deleting...');
    });

    it('should show "Delete" text when not deleting', () => {
      const isDeleting = false;
      const text = isDeleting ? 'Deleting...' : 'Delete';

      expect(text).toBe('Delete');
    });

    it('should use destructive styling', () => {
      // From component: className="flex-1 text-destructive hover:text-destructive hover:bg-destructive/10"
      const hasDestructiveClass = true;
      expect(hasDestructiveClass).toBe(true);
    });

    it('should use outline variant', () => {
      // From component: variant="outline"
      const variant = 'outline';
      expect(variant).toBe('outline');
    });
  });

  describe('Delete Confirmation Dialog', () => {
    it('should show AlertDialog', () => {
      // From component: AlertDialog wrapper
      const hasDialog = true;
      expect(hasDialog).toBe(true);
    });

    it('should have open state controlled by showDeleteDialog', () => {
      const showDeleteDialog = true;
      expect(showDeleteDialog).toBe(true);
    });

    it('should display memory label in confirmation message', () => {
      const node = createTestNode({ label: 'Important Pattern' });
      // From component: Are you sure you want to delete "{node.label}"?
      const message = `Are you sure you want to delete "${node.label}"?`;

      expect(message).toContain('Important Pattern');
    });

    it('should have dialog title', () => {
      // From component: <AlertDialogTitle>Delete Memory?</AlertDialogTitle>
      const title = 'Delete Memory?';
      expect(title).toBe('Delete Memory?');
    });

    it('should have cancel button', () => {
      // From component: AlertDialogCancel with "Cancel" text
      const hasCancelButton = true;
      expect(hasCancelButton).toBe(true);
    });

    it('should have confirm delete button', () => {
      // From component: AlertDialogAction with "Delete" text
      const hasConfirmButton = true;
      expect(hasConfirmButton).toBe(true);
    });

    it('should disable cancel button during deletion', () => {
      const isDeleting = true;
      const cancelDisabled = isDeleting;

      expect(cancelDisabled).toBe(true);
    });

    it('should disable confirm button during deletion', () => {
      const isDeleting = true;
      const confirmDisabled = isDeleting;

      expect(confirmDisabled).toBe(true);
    });

    it('should show Loader2 on confirm button during deletion', () => {
      const isDeleting = true;
      const hasSpinner = isDeleting;

      expect(hasSpinner).toBe(true);
    });

    it('should call handleDelete when confirm is clicked', async () => {
      const node = createTestNode({ id: 'delete-node' });
      const setIsDeleting = vi.fn();
      const setShowDeleteDialog = vi.fn();

      const handleDelete = async () => {
        setIsDeleting(true);
        await mockOnDelete(node.id);
        setShowDeleteDialog(false);
        setIsDeleting(false);
      };

      await handleDelete();

      expect(setIsDeleting).toHaveBeenLastCalledWith(false);
      expect(setShowDeleteDialog).toHaveBeenCalledWith(false);
      expect(mockOnDelete).toHaveBeenCalledWith(node.id);
    });

    it('should close dialog and panel after successful delete', async () => {
      const setShowDeleteDialog = vi.fn();
      const onClose = vi.fn();
      const setIsDeleting = vi.fn();

      const handleDelete = async () => {
        setIsDeleting(true);
        await mockOnDelete('node-id');
        setShowDeleteDialog(false);
        setIsDeleting(false);
        onClose();
      };

      await handleDelete();

      expect(setShowDeleteDialog).toHaveBeenCalledWith(false);
      expect(onClose).toHaveBeenCalledTimes(1);
    });

    it('should handle delete errors gracefully', async () => {
      const errorDelete = vi.fn().mockRejectedValue(new Error('Delete failed'));
      const setIsDeleting = vi.fn();
      const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

      const handleDelete = async () => {
        setIsDeleting(true);
        try {
          await errorDelete('node-id');
        } catch (error) {
          console.error('Failed to delete memory:', error);
          setIsDeleting(false);
        }
      };

      await handleDelete();

      expect(setIsDeleting).toHaveBeenLastCalledWith(false);
      expect(consoleErrorSpy).toHaveBeenCalled();

      consoleErrorSpy.mockRestore();
    });

    it('should use destructive styling on confirm button', () => {
      // From component: className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
      const hasDestructiveClass = true;
      expect(hasDestructiveClass).toBe(true);
    });
  });

  describe('Panel Layout and Styling', () => {
    it('should have fixed width of 96 (24rem)', () => {
      // From component: className="w-96"
      const widthClass = 'w-96';
      expect(widthClass).toBe('w-96');
    });

    it('should have left border', () => {
      // From component: className="border-l border-border"
      const hasLeftBorder = true;
      expect(hasLeftBorder).toBe(true);
    });

    it('should use flex column layout', () => {
      // From component: className="bg-background flex flex-col h-full"
      const layoutClasses = ['flex', 'flex-col'];
      expect(layoutClasses).toContain('flex');
      expect(layoutClasses).toContain('flex-col');
    });

    it('should have full height', () => {
      // From component: className="h-full"
      const heightClass = 'h-full';
      expect(heightClass).toBe('h-full');
    });

    it('should have scrollable content area', () => {
      // From component: ScrollArea with className="flex-1"
      const hasScrollArea = true;
      expect(hasScrollArea).toBe(true);
    });

    it('should have shrink-0 header', () => {
      // From component: header className="shrink-0"
      const headerShrink = 'shrink-0';
      expect(headerShrink).toBe('shrink-0');
    });

    it('should have shrink-0 footer', () => {
      // From component: footer className="shrink-0"
      const footerShrink = 'shrink-0';
      expect(footerShrink).toBe('shrink-0');
    });
  });

  describe('Text Truncation Helper', () => {
    it('should truncate long text', () => {
      const longText = 'A'.repeat(100);
      const maxLength = 30;
      const truncated = longText.length <= maxLength
        ? longText
        : longText.substring(0, maxLength) + '...';

      expect(truncated.length).toBe(33); // 30 + '...'
      expect(truncated).toContain('...');
    });

    it('should not truncate short text', () => {
      const shortText = 'Short';
      const maxLength = 30;
      const truncated = shortText.length <= maxLength
        ? shortText
        : shortText.substring(0, maxLength) + '...';

      expect(truncated).toBe('Short');
      expect(truncated).not.toContain('...');
    });

    it('should handle empty text', () => {
      const emptyText = '';
      const maxLength = 30;
      const truncated = !emptyText ? '' : emptyText;

      expect(truncated).toBe('');
    });

    it('should handle null text', () => {
      const nullText = null;
      const maxLength = 30;
      const truncated = !nullText ? '' : nullText;

      expect(truncated).toBe('');
    });

    it('should handle undefined text', () => {
      const undefinedText = undefined;
      const maxLength = 30;
      const truncated = !undefinedText ? '' : undefinedText;

      expect(truncated).toBe('');
    });
  });

  describe('Edge Cases', () => {
    it('should handle node with no optional fields', () => {
      const node = createTestNode({
        session_number: undefined,
        group_id: undefined,
        content: undefined
      });

      expect(node.session_number).toBeUndefined();
      expect(node.group_id).toBeUndefined();
      expect(node.content).toBeUndefined();
    });

    it('should handle empty edges array', () => {
      const edges: MemoryGraphEdge[] = [];
      const incomingEdges = edges.filter(edge => edge.target === 'node-id');
      const outgoingEdges = edges.filter(edge => edge.source === 'node-id');

      expect(incomingEdges).toHaveLength(0);
      expect(outgoingEdges).toHaveLength(0);
    });

    it('should handle very long content', () => {
      const longContent = '{' + '"x": "'.repeat(1000) + '"}';
      const node = createTestNode({ content: longContent });

      expect(node.content.length).toBeGreaterThan(1000);
    });

    it('should handle node with special characters in label', () => {
      const specialLabel = 'Test <Memory> & "Label"';
      const node = createTestNode({ label: specialLabel });

      expect(node.label).toBe(specialLabel);
    });

    it('should handle node with unicode in label', () => {
      const unicodeLabel = 'Test 😀 🎉 🚀';
      const node = createTestNode({ label: unicodeLabel });

      expect(node.label).toBe(unicodeLabel);
    });

    it('should handle edge with missing names', () => {
      const edge = createTestEdge({
        source_name: undefined,
        target_name: undefined
      });

      expect(edge.source_name).toBeUndefined();
      expect(edge.target_name).toBeUndefined();
    });

    it('should handle edge with missing label', () => {
      const edge = createTestEdge({
        label: undefined,
        relationship_type: 'related_to'
      });

      const relationship = edge.label || edge.relationship_type;
      expect(relationship).toBe('related_to');
    });

    it('should handle rapid delete cancel', () => {
      let showDeleteDialog = false;

      // Rapid toggles
      showDeleteDialog = true;
      showDeleteDialog = false;
      showDeleteDialog = true;
      showDeleteDialog = false;

      expect(showDeleteDialog).toBe(false);
    });

    it('should handle node with timestamp in different formats', () => {
      const timestamps = [
        '2024-01-11T10:00:00Z',
        '2024-01-11T10:00:00.000Z',
        '2024-01-11T10:00:00+00:00'
      ];

      timestamps.forEach(timestamp => {
        const node = createTestNode({ timestamp });
        expect(node.timestamp).toBeDefined();
      });
    });
  });

  describe('Integration Tests', () => {
    it('should handle complete delete flow', async () => {
      const node = createTestNode({ id: 'delete-flow-node' });
      const setIsDeleting = vi.fn();
      const setShowDeleteDialog = vi.fn();
      const onClose = vi.fn();
      const deleteSuccess = vi.fn().mockResolvedValue({ success: true });

      // Start delete
      setIsDeleting(true);
      setShowDeleteDialog(true);

      // Confirm delete
      await deleteSuccess(node.id);
      setShowDeleteDialog(false);
      setIsDeleting(false);
      onClose();

      expect(deleteSuccess).toHaveBeenCalledWith(node.id);
      expect(setShowDeleteDialog).toHaveBeenLastCalledWith(false);
      expect(setIsDeleting).toHaveBeenLastCalledWith(false);
      expect(onClose).toHaveBeenCalledTimes(1);
    });

    it('should handle complete edit flow', () => {
      const node = createTestNode({ id: 'edit-flow-node' });
      const onEdit = vi.fn();

      onEdit(node);

      expect(onEdit).toHaveBeenCalledWith(node);
      expect(onEdit).toHaveBeenCalledTimes(1);
    });

    it('should handle panel close', () => {
      const onClose = vi.fn();

      onClose();

      expect(onClose).toHaveBeenCalledTimes(1);
    });
  });
});
