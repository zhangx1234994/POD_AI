/// <reference types="react" />
/// <reference types="react-dom" />

declare module '*.svg';
declare module '*.png';
declare module '*.jpg';
declare module '*.jpeg';
declare module '*.gif';
declare module '*.webp';

declare namespace JSX {
  interface IntrinsicElements {
    [elemName: string]: any;
  }
}
