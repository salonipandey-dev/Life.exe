// Minimal React 19 type declarations for environments where @types/react
// cannot be installed. Covers exactly the API surface this app uses.
// With network access, prefer `npm i` + `npm run typecheck` (real types).

declare module "react" {
  export type ReactNode = JSX.Element | string | number | boolean | null | undefined | ReactNode[];
  export type SetStateAction<S> = S | ((prev: S) => S);
  export type Dispatch<A> = (value: A) => void;
  export interface MutableRefObject<T> { current: T }
  export interface Context<T> { Provider: (props: { value: T; children?: ReactNode }) => JSX.Element }
  export function useState<S>(initial: S | (() => S)): [S, Dispatch<SetStateAction<S>>];
  export function useEffect(effect: () => void | (() => void), deps?: readonly unknown[]): void;
  export function useLayoutEffect(effect: () => void | (() => void), deps?: readonly unknown[]): void;
  export function useMemo<T>(factory: () => T, deps: readonly unknown[]): T;
  export function useCallback<T extends (...args: never[]) => unknown>(fn: T, deps: readonly unknown[]): T;
  export function useRef<T>(initial: T): MutableRefObject<T>;
  export function useId(): string;
  export function useSyncExternalStore<T>(subscribe: (cb: () => void) => () => void, getSnapshot: () => T): T;
  export function createContext<T>(value: T): Context<T>;
  export function useContext<T>(context: Context<T>): T;
  export const StrictMode: (props: { children?: ReactNode }) => JSX.Element;
  export const Fragment: (props: { children?: ReactNode }) => JSX.Element;
  export interface FormEvent { preventDefault(): void }
  export interface KeyboardEvent { key: string; preventDefault(): void }
  export interface ChangeEvent<T = HTMLInputElement> { target: T }
}

declare module "react/jsx-runtime" {
  export const jsx: unknown;
  export const jsxs: unknown;
  export const Fragment: unknown;
}

declare module "react-dom/client" {
  export function createRoot(el: Element): { render(node: unknown): void };
}

declare namespace JSX {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  type Element = any;
  interface ElementChildrenAttribute { children: unknown }
  interface IntrinsicAttributes { key?: string | number | null }
  interface IntrinsicElements {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    [name: string]: any;
  }
}
