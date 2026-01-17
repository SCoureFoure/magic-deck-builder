import type { MouseEvent as ReactMouseEvent, ReactNode } from "react";

export type CardFace = {
  name?: string;
  oracle_text?: string | null;
  type_line?: string;
  mana_cost?: string;
  image_uris?: { normal?: string; large?: string } | null;
};

export type CardDisplayData = {
  name: string;
  type_line: string;
  mana_cost: string | null;
  cmc: number;
  oracle_text?: string | null;
  image_url?: string | null;
  card_faces?: CardFace[] | null;
};

type CardDisplayProps = {
  card: CardDisplayData;
  variant: "compact" | "detailed";
  showOracle?: boolean;
  className?: string;
  faceLayout?: "stack" | "row";
  onImageClick?: (
    event: ReactMouseEvent<HTMLImageElement>,
    imageUrl: string | null,
    alt: string
  ) => void;
  children?: ReactNode;
};

const hasFaceDetails = (faces: CardFace[]) =>
  faces.some(
    (face) =>
      face.oracle_text ||
      face.image_uris ||
      face.type_line ||
      face.mana_cost ||
      face.name,
  );

const buildMeta = (mana_cost: string | null, cmc: number) =>
  mana_cost ? `${mana_cost} (${cmc})` : `${cmc}`;

export function CardDisplay({
  card,
  variant,
  showOracle = false,
  className,
  faceLayout = "stack",
  onImageClick,
  children,
}: CardDisplayProps) {
  const faces = card.card_faces ?? [];
  const hasFaces = hasFaceDetails(faces);

  if (hasFaces && variant === "detailed") {
    return (
      <article className={`training-card training-card-faces ${className ?? ""}`.trim()}>
        {faces.map((face, index) => {
          const faceImage =
            face.image_uris?.large ?? face.image_uris?.normal ?? card.image_url ?? null;
          const faceName = face.name ?? card.name;
          const faceType = face.type_line ?? card.type_line;
          const faceCost = face.mana_cost ?? card.mana_cost;
          const faceText = face.oracle_text ?? (index === 0 ? card.oracle_text : null);

          return (
            <div key={`${card.name}-face-${index}`} className="training-face">
              {faceImage ? (
                <img
                  src={faceImage}
                  alt={faceName}
                  loading="lazy"
                  onClick={(event) => onImageClick?.(event, faceImage, faceName)}
                />
              ) : (
                <div className="deck-card-placeholder">No image</div>
              )}
              <div>
                <h3>{faceName}</h3>
                <p className="muted">{faceType}</p>
                <p className="meta">{buildMeta(faceCost, card.cmc)}</p>
                {showOracle && faceText && <p className="oracle-text">{faceText}</p>}
                {children && index === 0 ? children : null}
              </div>
            </div>
          );
        })}
      </article>
    );
  }

  if (hasFaces && variant === "compact") {
    return (
      <article
        className={`deck-card-faces ${faceLayout === "row" ? "row" : ""} ${
          className ?? ""
        }`.trim()}
      >
        {faces.map((face, index) => {
          const faceImage =
            face.image_uris?.large ?? face.image_uris?.normal ?? card.image_url ?? null;
          const faceName = face.name ?? card.name;
          const faceType = face.type_line ?? card.type_line;
          const faceCost = face.mana_cost ?? card.mana_cost;
          const faceText = face.oracle_text ?? (index === 0 ? card.oracle_text : null);

          return (
            <div key={`${card.name}-face-${index}`} className="deck-card deck-card-face">
              {faceImage ? (
                <img
                  src={faceImage}
                  alt={faceName}
                  loading="lazy"
                  onClick={(event) => onImageClick?.(event, faceImage, faceName)}
                />
              ) : (
                <div className="deck-card-placeholder">No image</div>
              )}
              <div>
                <h4>{faceName}</h4>
                <p className="muted">{faceType}</p>
                <p className="meta">{buildMeta(faceCost, card.cmc)}</p>
                {showOracle && faceText && <p className="oracle-text">{faceText}</p>}
                {children && index === 0 ? children : null}
              </div>
            </div>
          );
        })}
      </article>
    );
  }

  if (variant === "detailed") {
    return (
      <article className={`training-card ${className ?? ""}`.trim()}>
        {card.image_url ? (
          <img
            src={card.image_url}
            alt={card.name}
            loading="lazy"
            onClick={(event) => onImageClick?.(event, card.image_url ?? null, card.name)}
          />
        ) : (
          <div className="deck-card-placeholder">No image</div>
        )}
        <div>
          <h3>{card.name}</h3>
          <p className="muted">{card.type_line}</p>
          <p className="meta">{buildMeta(card.mana_cost, card.cmc)}</p>
          {showOracle && card.oracle_text && (
            <p className="oracle-text">{card.oracle_text}</p>
          )}
          {children}
        </div>
      </article>
    );
  }

  return (
    <article className={`deck-card ${className ?? ""}`.trim()}>
      {card.image_url ? (
        <img
          src={card.image_url}
          alt={card.name}
          loading="lazy"
          onClick={(event) => onImageClick?.(event, card.image_url ?? null, card.name)}
        />
      ) : (
        <div className="deck-card-placeholder">No image</div>
      )}
      <div>
        <h4>{card.name}</h4>
        <p className="muted">{card.type_line}</p>
        <p className="meta">{buildMeta(card.mana_cost, card.cmc)}</p>
        {showOracle && card.oracle_text && <p className="oracle-text">{card.oracle_text}</p>}
        {children}
      </div>
    </article>
  );
}
