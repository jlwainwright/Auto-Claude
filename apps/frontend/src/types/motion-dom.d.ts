declare module 'motion-dom' {
  export type AnyResolvedKeyframe = any;
  export type AnimationDefinition = any;
  export type AnimationOptions = any;
  export type AnimationPlaybackControls = any;
  export type AnimationPlaybackControlsWithThen = any;
  export type AnimationPlaybackOptions = any;
  export type AnimationScope = any;
  export type DOMKeyframesDefinition = any;
  export type ElementOrSelector = any;
  export type EventInfo = any;
  export type GroupAnimationWithThen = any;
  export type JSAnimation = any;
  export type KeyframeResolver<V = any> = any;
  export type LegacyAnimationControls = any;
  export type MotionValueEventCallbacks = any;
  export type OnKeyframesResolved<V = any> = any;
  export type SpringOptions = any;
  export type TargetAndTransition = any;
  export type TransformOptions = any;
  export type Transition = any;
  export type UnresolvedValueKeyframe = any;
  export type ValueAnimationTransition = any;
  export type ValueTransition = any;

  export interface MotionValue<T = any> {
    get(): T;
    set(value: T): void;
  }

  export interface TransformProperties {
    x?: number | string;
    y?: number | string;
    z?: number | string;
    translateX?: number | string;
    translateY?: number | string;
    translateZ?: number | string;
    scale?: number;
    scaleX?: number;
    scaleY?: number;
    scaleZ?: number;
    rotate?: number | string;
    rotateX?: number | string;
    rotateY?: number | string;
    rotateZ?: number | string;
    skew?: number | string;
    skewX?: number | string;
    skewY?: number | string;
    transformPerspective?: number | string;
  }

  export interface SVGPathProperties {
    pathLength?: number;
    pathOffset?: number;
    pathSpacing?: number;
  }

  export type Batcher = any;

  export interface MotionNodeOptions {
    // Animation/variants
    initial?: any;
    animate?: any;
    exit?: any;
    variants?: any;
    transition?: any;
    custom?: any;
    inherit?: boolean;

    // Interaction
    whileHover?: any;
    whileTap?: any;
    whileFocus?: any;
    whileInView?: any;
    viewport?: any;

    // Layout/drag
    layout?: any;
    layoutId?: string;
    drag?: any;
    dragConstraints?: any;
    dragElastic?: any;
    dragMomentum?: any;
    dragTransition?: any;
    whileDrag?: any;

    // Callbacks
    onAnimationStart?: any;
    onAnimationComplete?: any;
    onUpdate?: any;
    onLayoutAnimationStart?: any;
    onLayoutAnimationComplete?: any;
    onHoverStart?: any;
    onHoverEnd?: any;
    onTapStart?: any;
    onTap?: any;
    onTapCancel?: any;
    onPanStart?: any;
    onPan?: any;
    onPanEnd?: any;
    onDragStart?: any;
    onDrag?: any;
    onDragEnd?: any;
    onViewportEnter?: any;
    onViewportLeave?: any;
  }
}
