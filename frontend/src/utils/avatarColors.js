/**
 * avatarColors.js - Deterministic Avatar Gradient Generation
 * 
 * Generates consistent two-tone gradient colors for contact avatars based on sender name.
 * Same sender always gets same gradient (deterministic hashing).
 * 
 * Part of the neumorphic dark gradient design system migration.
 */

/**
 * Avatar gradient palette (6 color pairs)
 * Each pair has a base color and lighter variant for gradient
 */
const AVATAR_PALETTE = [
  {
    id: 'orange',
    base: '#F97316',
    light: '#FB923C',
    tailwind: { from: 'from-[#F97316]', to: 'to-[#FB923C]' }
  },
  {
    id: 'pink',
    base: '#EC4899',
    light: '#F472B6',
    tailwind: { from: 'from-[#EC4899]', to: 'to-[#F472B6]' }
  },
  {
    id: 'cyan',
    base: '#06B6D4',
    light: '#22D3EE',
    tailwind: { from: 'from-[#06B6D4]', to: 'to-[#22D3EE]' }
  },
  {
    id: 'green',
    base: '#10B981',
    light: '#34D399',
    tailwind: { from: 'from-[#10B981]', to: 'to-[#34D399]' }
  },
  {
    id: 'purple',
    base: '#A855F7',
    light: '#C084FC',
    tailwind: { from: 'from-[#A855F7]', to: 'to-[#C084FC]' }
  },
  {
    id: 'yellow',
    base: '#EAB308',
    light: '#FACC15',
    tailwind: { from: 'from-[#EAB308]', to: 'to-[#FACC15]' }
  }
];

/**
 * Simple hash function to convert string to number
 * @param {string} str - Input string (sender name/email)
 * @returns {number} Hash value
 */
function hashString(str) {
  if (!str || typeof str !== 'string') return 0;
  
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    const char = str.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash = hash & hash; // Convert to 32-bit integer
  }
  return Math.abs(hash);
}

/**
 * Get avatar gradient for a sender (deterministic)
 * Same sender always gets same gradient
 * 
 * @param {string} sender - Sender name or email
 * @returns {Object} Gradient object with base, light, and Tailwind classes
 * 
 * @example
 * const gradient = getAvatarGradient('John Doe');
 * // Use with inline styles:
 * style={{ background: `linear-gradient(135deg, ${gradient.base} 0%, ${gradient.light} 100%)` }}
 * 
 * // Or with Tailwind classes:
 * className={`bg-gradient-to-br ${gradient.tailwind.from} ${gradient.tailwind.to}`}
 */
export function getAvatarGradient(sender) {
  const hash = hashString(sender);
  const index = hash % AVATAR_PALETTE.length;
  return AVATAR_PALETTE[index];
}

/**
 * Get avatar initials from sender name/email
 * @param {string} sender - Sender name or email
 * @returns {string} 1-2 character initials
 * 
 * @example
 * getInitials('John Doe') // 'JD'
 * getInitials('john@example.com') // 'J'
 * getInitials('Sarah Johnson') // 'SJ'
 */
export function getInitials(sender) {
  if (!sender || typeof sender !== 'string') return '?';
  
  // Remove email domain if present
  const name = sender.split('@')[0].split('<')[0].trim();
  
  // Split by spaces or common separators
  const parts = name.split(/[\s._-]+/).filter(p => p.length > 0);
  
  if (parts.length === 0) return '?';
  if (parts.length === 1) return parts[0].charAt(0).toUpperCase();
  
  // Take first letter of first and last part
  return (parts[0].charAt(0) + parts[parts.length - 1].charAt(0)).toUpperCase();
}

/**
 * Get complete avatar props for rendering
 * @param {string} sender - Sender name or email
 * @returns {Object} Avatar props including gradient, initials, and inline style
 * 
 * @example
 * const avatar = getAvatarProps('Sarah Johnson');
 * <div 
 *   className={`w-10 h-10 rounded-full bg-gradient-to-br ${avatar.gradient.tailwind.from} ${avatar.gradient.tailwind.to}`}
 * >
 *   {avatar.initials}
 * </div>
 */
export function getAvatarProps(sender) {
  const gradient = getAvatarGradient(sender);
  const initials = getInitials(sender);
  
  return {
    gradient,
    initials,
    // Inline style for non-Tailwind usage
    style: {
      background: `linear-gradient(135deg, ${gradient.base} 0%, ${gradient.light} 100%)`
    }
  };
}

/**
 * Export the palette for reference/testing
 */
export { AVATAR_PALETTE };
